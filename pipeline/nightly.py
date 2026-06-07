"""Nightly ingestion entrypoint.

Refresh every seeded agent. Auto-discover new candidates per category.
Classify, score, truncate to top 250, and write JSON. Drops are recorded
in catalog/_dropped/<date>.json for auditability.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.progress import Progress

from pipeline.budget import from_env as budget_from_env
from pipeline.budget import set_budget
from pipeline.build import (
    build_from_github,
    build_from_huggingface,
    merge_benchmarks,
    merge_overrides,
)
from pipeline.classifier import classify_with_hint
from pipeline.crawlers import github as gh
from pipeline.crawlers import huggingface as hf
from pipeline.paths import CATALOG_DIR, DROPPED_DIR
from pipeline.ranking import rank_category
from pipeline.report import write_report
from pipeline.schema import Agent, Category, CategoryIndex
from pipeline.store import (
    iter_catalog_files,
    load_agent_file,
    load_categories,
    load_seeds,
    write_agent,
)

TOP_N = 500
# Per-category overrides for the featured cap. Empty by default — every
# category gets the 500-entry default. Add slugs here to raise (or lower)
# specific categories. Discovery overflow past the cap that still passes
# TAIL_QUALITY_THRESHOLD goes to catalog/<cat>/_tail/.
PER_CATEGORY_FEATURED_CAP: dict[str, int] = {}

# Hard cap on per-run classifier (OpenAI) calls. Stops runaway cost if a
# future query expansion makes broad-discovery surface explode; once hit,
# subsequent broad-query repos keep their query-origin category. Tune via
# ONEXUS_CLASSIFIER_MAX env var if you want more/fewer reclassifications.
CLASSIFIER_MAX_PER_RUN = 2000
# Entries past the featured cap that still pass the quality threshold go to
# catalog/<cat>/_tail/ — visible to site loaders that opt in but skipped by
# the validator's `_`-dir filter (PR #44). Entries below threshold land in
# catalog/_dropped/<date>.json as before.
TAIL_CAP = 1000
TAIL_QUALITY_THRESHOLD = 0.20
console = Console()


def _broaden_queries(cat: Category) -> list[str]:
    """Auto-generate broader GitHub queries from each category's seed_keywords.

    The hand-curated `github_search_queries` are mostly `topic:X` filters that
    only match repos whose author specifically tagged that niche topic. Most
    real agent repos don't. This function adds name/description and README
    fallbacks at a low star floor so undersampled categories actually fill.

    Cheap: each variant is one search call (1 of ~30k budget); dedupe in
    `_discover` prevents extra repo fetches for results already seen.
    """
    extra: list[str] = []
    seen: set[str] = set(cat.github_search_queries)
    for kw in cat.seed_keywords:
        for tmpl in (
            f'"{kw}" in:name,description stars:>5',
            f'"{kw}" in:readme stars:>10',
        ):
            if tmpl not in seen:
                extra.append(tmpl)
                seen.add(tmpl)
    return extra


def _index_existing() -> dict[tuple[str, str], Agent]:
    """Map (category, slug) -> Agent for the on-disk catalog."""
    out: dict[tuple[str, str], Agent] = {}
    for f in iter_catalog_files():
        try:
            agent = load_agent_file(f)
            out[(agent.category, agent.slug)] = agent
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]skip {f}: {e}")
    return out


def _refresh_seeds(
    client: httpx.Client,
    categories: CategoryIndex,
    existing: dict[tuple[str, str], Agent],
    by_cat: dict[str, list[Agent]],
    *,
    dry_run: bool,
) -> None:
    for cat in categories.categories:
        for entry in load_seeds(cat.slug):
            agent = _refresh_one_seed(client, cat.slug, entry, existing, dry_run)
            if agent:
                by_cat[cat.slug].append(agent)


def _refresh_one_seed(
    client: httpx.Client,
    cat_slug: str,
    entry: dict,
    existing: dict[tuple[str, str], Agent],
    dry_run: bool,
) -> Agent | None:
    src = entry.get("source")
    runnable = bool(entry.get("runnable"))
    adapter_ref = entry.get("adapter_ref")
    notes = entry.get("notes")

    try:
        if src == "github":
            repo = entry["repo"]
            prior = next(
                (a for (c, _), a in existing.items() if c == cat_slug and a.source.github == repo),
                None,
            )
            agent = build_from_github(
                client,
                repo,
                cat_slug,
                runnable=runnable,
                adapter_ref=adapter_ref,
                notes=notes,
                discovered_via="seed",
                existing_first_seen=prior.first_seen_at if prior else None,
            )
        elif src == "huggingface":
            model_id = entry["model"]
            prior = next(
                (
                    a
                    for (c, _), a in existing.items()
                    if c == cat_slug and a.source.huggingface == model_id
                ),
                None,
            )
            agent = build_from_huggingface(
                client,
                model_id,
                cat_slug,
                runnable=runnable,
                adapter_ref=adapter_ref,
                notes=notes,
                discovered_via="seed",
                existing_first_seen=prior.first_seen_at if prior else None,
            )
        else:
            console.print(f"[yellow]unknown source for {entry}: {src}")
            return None
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]seed refresh failed for {entry}: {e}")
        # Fall back to the prior on-disk entry so transient API errors don't drop it.
        if src == "github":
            return next(
                (a for (c, _), a in existing.items() if c == cat_slug and a.source.github == entry.get("repo")),
                None,
            )
        if src == "huggingface":
            return next(
                (a for (c, _), a in existing.items() if c == cat_slug and a.source.huggingface == entry.get("model")),
                None,
            )
        return None

    if agent:
        merge_benchmarks(agent, prior)
        merge_overrides(agent, prior)
    return agent


def _discover(
    client: httpx.Client,
    categories: CategoryIndex,
    existing: dict[tuple[str, str], Agent],
    by_cat: dict[str, list[Agent]],
    *,
    per_query_limit: int,
    dry_run: bool,
) -> dict[str, int]:
    seen_gh: set[str] = {a.source.github for ags in by_cat.values() for a in ags if a.source.github}
    seen_hf: set[str] = {
        a.source.huggingface for ags in by_cat.values() for a in ags if a.source.huggingface
    }
    classifier_ok = 0
    classifier_err = 0
    classifier_capped = 0
    classifier_first_errors: list[str] = []
    classifier_max = int(os.environ.get("ONEXUS_CLASSIFIER_MAX") or CLASSIFIER_MAX_PER_RUN)
    for cat in categories.categories:
        curated_queries = list(cat.github_search_queries)
        broad_queries = _broaden_queries(cat)
        broad_set = set(broad_queries)
        for q in curated_queries + broad_queries:
            is_broad = q in broad_set
            try:
                hits = gh.search_repos(client, q, limit=per_query_limit)
            except Exception as e:  # noqa: BLE001
                console.print(f"[yellow]gh search '{q}' failed: {e}")
                continue
            for repo in hits:
                if repo in seen_gh:
                    continue
                seen_gh.add(repo)
                prior = next(
                    (a for (c, _), a in existing.items() if c == cat.slug and a.source.github == repo),
                    None,
                )
                try:
                    agent = build_from_github(
                        client,
                        repo,
                        cat.slug,
                        discovered_via="auto",
                        existing_first_seen=prior.first_seen_at if prior else None,
                    )
                except Exception as e:  # noqa: BLE001
                    console.print(f"[yellow]gh build failed for {repo}: {e}")
                    continue
                if not agent:
                    continue
                merge_benchmarks(agent, prior)
                merge_overrides(agent, prior)
                # Broad queries have weaker category precision than the
                # hand-curated topic:X filters. Validate the query-origin
                # category via keyword classifier, falling back to OpenAI
                # gpt-5.4-mini only for the ambiguous cases.
                actual_cat = cat.slug
                if is_broad and (classifier_ok + classifier_err) < classifier_max:
                    text = f"{agent.tagline} | tags: {' '.join(agent.tags)}"
                    result = classify_with_hint(text, categories, cat.slug)
                    if result.reason.startswith("openai:"):
                        # Successful openai response sets category. Errors return
                        # category=None and reason like "openai: AuthError: ..."
                        if result.category:
                            classifier_ok += 1
                        else:
                            classifier_err += 1
                            if len(classifier_first_errors) < 3:
                                classifier_first_errors.append(result.reason)
                    if result.category and result.category != cat.slug:
                        agent.category = result.category
                        actual_cat = result.category
                elif is_broad:
                    classifier_capped += 1
                by_cat[actual_cat].append(agent)

        hf_tags = (cat.huggingface_filters or {}).get("tags") or []
        if hf_tags:
            try:
                model_ids = hf.search_models(client, hf_tags, limit=per_query_limit)
            except Exception as e:  # noqa: BLE001
                console.print(f"[yellow]hf search {hf_tags} failed: {e}")
                model_ids = []
            for mid in model_ids:
                if mid in seen_hf:
                    continue
                seen_hf.add(mid)
                prior = next(
                    (
                        a
                        for (c, _), a in existing.items()
                        if c == cat.slug and a.source.huggingface == mid
                    ),
                    None,
                )
                try:
                    agent = build_from_huggingface(
                        client,
                        mid,
                        cat.slug,
                        discovered_via="auto",
                        existing_first_seen=prior.first_seen_at if prior else None,
                    )
                except Exception as e:  # noqa: BLE001
                    console.print(f"[yellow]hf build failed for {mid}: {e}")
                    continue
                if agent:
                    merge_benchmarks(agent, prior)
                    merge_overrides(agent, prior)
                    by_cat[cat.slug].append(agent)

        if classifier_ok or classifier_err:
            console.print(
                f"[dim]classifier · openai ok={classifier_ok} err={classifier_err}"
                + (f" capped={classifier_capped}" if classifier_capped else "")
            )

    for msg in classifier_first_errors:
        console.print(f"[yellow]classifier first errors · {msg}")
    return {
        "classifier_ok": classifier_ok,
        "classifier_err": classifier_err,
        "classifier_capped": classifier_capped,
    }


def _write_and_truncate(
    by_cat: dict[str, list[Agent]],
    categories: CategoryIndex,
    *,
    dry_run: bool,
) -> dict[str, list[str]]:
    """Score, truncate, write. Returns dropped slugs per category.

    Three-tier output per category:
      catalog/<cat>/<slug>.json         featured (top featured_cap by score)
      catalog/<cat>/_tail/<slug>.json   tail (past cap but score >= threshold,
                                        up to TAIL_CAP total)
      catalog/_dropped/<date>.json      audit log of slugs we cut entirely
    """
    cat_lookup: dict[str, Category] = {c.slug: c for c in categories.categories}
    dropped: dict[str, list[str]] = {}

    for cat_slug, agents in by_cat.items():
        cat = cat_lookup.get(cat_slug)
        if not cat:
            continue

        # Deduplicate by slug, preferring seed over auto
        by_slug: dict[str, Agent] = {}
        for a in agents:
            existing = by_slug.get(a.slug)
            if not existing or (a.discovered_via == "seed" and existing.discovered_via != "seed"):
                by_slug[a.slug] = a
        deduped = list(by_slug.values())

        ranked = rank_category(deduped, cat)
        featured_cap = PER_CATEGORY_FEATURED_CAP.get(cat_slug, TOP_N)
        featured = ranked[:featured_cap]
        tail_candidates = ranked[featured_cap : featured_cap + TAIL_CAP]
        tail = [a for a in tail_candidates if a.composite_score >= TAIL_QUALITY_THRESHOLD]
        cut = [
            a
            for a in ranked[featured_cap:]
            if a not in tail
        ]

        if cut:
            dropped[cat_slug] = [a.slug for a in cut]

        if dry_run:
            console.print(
                f"[cyan]{cat_slug}: would keep featured={len(featured)} "
                f"tail={len(tail)} drop={len(cut)}"
            )
            continue

        # Wipe the existing category dir so removed entries actually disappear,
        # but preserve _tail/ — we wipe that separately below.
        cat_dir = CATALOG_DIR / cat_slug
        if cat_dir.exists():
            for f in cat_dir.glob("*.json"):
                f.unlink()

        tail_dir = cat_dir / "_tail"
        if tail_dir.exists():
            for f in tail_dir.glob("*.json"):
                f.unlink()

        for a in featured:
            write_agent(a)

        if tail:
            tail_dir.mkdir(parents=True, exist_ok=True)
            for a in tail:
                (tail_dir / f"{a.slug}.json").write_text(
                    a.model_dump_json(indent=2, exclude_none=False) + "\n"
                )

    return dropped


def _record_drops(dropped: dict[str, list[str]]) -> Path | None:
    if not any(dropped.values()):
        return None
    DROPPED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out = DROPPED_DIR / f"{today}.json"
    payload = {"generated_at": datetime.now(UTC).isoformat(), "dropped": dropped}
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return out


@click.command()
@click.option("--dry-run", is_flag=True, help="Compute everything; write nothing.")
@click.option("--seeds-only", is_flag=True, help="Skip auto-discovery; refresh seeds only.")
@click.option("--per-query-limit", default=30, show_default=True, help="Results per search query.")
@click.option(
    "--categories", "category_filter", multiple=True, help="Limit to specific category slugs."
)
def main(
    dry_run: bool,
    seeds_only: bool,
    per_query_limit: int,
    category_filter: tuple[str, ...],
) -> None:
    """Run the nightly catalog refresh."""
    console.print(f"[bold]ONEXUS-Agents nightly[/] · dry_run={dry_run} · seeds_only={seeds_only}")
    budget = budget_from_env()
    set_budget(budget)
    console.print(f"[dim]budget · gh={budget.gh_remaining} hf={budget.hf_remaining}")
    cats = load_categories()
    if category_filter:
        cats.categories = [c for c in cats.categories if c.slug in category_filter]

    existing = _index_existing()
    prev_agents = list(existing.values())  # snapshot before this run rewrites catalog
    by_cat: dict[str, list[Agent]] = defaultdict(list)
    discover_stats: dict[str, int] = {"classifier_ok": 0, "classifier_err": 0, "classifier_capped": 0}

    with httpx.Client() as client, Progress() as progress:
        t1 = progress.add_task("refresh seeds", total=1)
        _refresh_seeds(client, cats, existing, by_cat, dry_run=dry_run)
        progress.advance(t1)

        if not seeds_only:
            t2 = progress.add_task("auto-discover", total=1)
            discover_stats = _discover(client, cats, existing, by_cat, per_query_limit=per_query_limit, dry_run=dry_run)
            progress.advance(t2)

        # Preserve prior on-disk entries that this run didn't refresh. A failed
        # GitHub fetch (rate limit, transient outage) makes build_from_github
        # return None, which would otherwise drop the entry from by_cat and let
        # _write_and_truncate's dir-wipe delete it. The catalog must only shrink
        # via ranking, never via missing API responses.
        seen = {(c, a.slug) for c, ags in by_cat.items() for a in ags}
        for (c, slug), agent in existing.items():
            if (c, slug) not in seen:
                by_cat[c].append(agent)

        t3 = progress.add_task("score + write", total=1)
        dropped = _write_and_truncate(by_cat, cats, dry_run=dry_run)
        progress.advance(t3)

    drops_file = _record_drops(dropped) if not dry_run else None
    total_kept = sum(min(len(v), TOP_N) for v in by_cat.values())
    console.print(f"[green]Done.[/] {total_kept} agents across {len(by_cat)} categories.")
    console.print(f"[dim]budget left · gh={budget.gh_remaining} hf={budget.hf_remaining}")
    if drops_file:
        console.print(f"Drops recorded in {drops_file.relative_to(CATALOG_DIR.parent)}")

    # Stats file is read by the cost-guard workflow step to fail the job on
    # threshold breaches. Path is repo-root so CI doesn't need to know which
    # subdir we wrote it to.
    final_stats = {
        "total_kept": total_kept,
        "category_count": len(by_cat),
        "budget_remaining_gh": budget.gh_remaining,
        "budget_remaining_hf": budget.hf_remaining,
        **discover_stats,
    }
    stats_path = CATALOG_DIR.parent / "_run_stats.json"
    stats_path.write_text(json.dumps(final_stats, indent=2) + "\n")

    # Daily quality summary. Written alongside the catalog so it lands in
    # the same auto-merge PR. Skip on dry-run since the catalog is unchanged.
    if not dry_run:
        # Flatten by_cat using each agent's category attribute, which may have
        # been reassigned by the classifier during _discover. Counting against
        # cat slugs in by_cat would miscount the reassignments.
        new_agents = [a for ags in by_cat.values() for a in ags]
        report_path = write_report(new_agents, prev_agents, final_stats, cap_per_cat=TOP_N)
        console.print(f"[dim]report written → {report_path.relative_to(CATALOG_DIR.parent)}")


if __name__ == "__main__":
    main()
