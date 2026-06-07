"""Weekly rescan — runnable detection + Tier 2 enrichment.

Two passes over the existing catalog, sharing a single API budget:

  1. Runnable rescan (cheap): for every entry not already flagged runnable,
     fetch the README once and re-run detect_mcp_runnability with the
     expanded README-aware detector. README fetch is reused by the enrich
     pass below so we don't pay for it twice.

  2. Tier 2 enrichment (capped): for the staleest N entries (by
     last_refreshed_at), populate contributors_count, releases_total,
     latest_release_at, commits_90d, has_ci, readme_length.

Both passes respect pipeline.budget, so a runaway crawl can't blow past
the free-tier rate window. On exhaustion, the remaining entries are left
untouched and the loop exits cleanly — next week's run picks up where
this one left off.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
import httpx
from rich.console import Console

from pipeline.budget import from_env as budget_from_env
from pipeline.budget import set_budget
from pipeline.build import detect_mcp_runnability
from pipeline.crawlers import github as gh
from pipeline.frameworks import detect_frameworks
from pipeline.schema import Agent
from pipeline.store import iter_catalog_files, load_agent_file

console = Console()


def _save(path: Path, agent: Agent) -> None:
    path.write_text(agent.model_dump_json(indent=2, exclude_none=False) + "\n")


def _rescan_runnable(client: httpx.Client, agent: Agent) -> tuple[bool, str | None]:
    """Re-derive runnable+adapter_ref using tags + README. Returns the new pair."""
    # Hand-set seed agents have notes-driven runnable status (adapters/<x>/mcp.json
    # entries). Never demote those — only ever flip false→true.
    if agent.runnable:
        return agent.runnable, agent.adapter_ref

    readme: str | None = None
    if agent.source.primary == "github" and agent.source.github:
        readme = gh.fetch_readme(client, agent.source.github)
    return detect_mcp_runnability(agent.tags, readme=readme)


def _enrich(client: httpx.Client, agent: Agent) -> None:
    """Populate Tier 2 metrics in-place. Each helper spends one API call."""
    if agent.source.primary != "github" or not agent.source.github:
        return  # Tier 2 enrichment is GH-only for now
    repo = agent.source.github
    m = agent.metrics

    m.contributors_count = gh.count_contributors(client, repo)

    rs = gh.fetch_releases_summary(client, repo)
    if rs is not None:
        m.releases_total = rs["total"]
        m.latest_release_at = rs["latest_at"]

    since = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    m.commits_90d = gh.count_commits_since(client, repo, since)

    m.has_ci = gh.has_ci_workflows(client, repo)

    readme = gh.fetch_readme(client, repo)
    if readme is not None:
        m.readme_length = len(readme)
        # README-aware framework detection refines what nightly's tag/tagline
        # pass already populated. Union — never demote a tag-derived hit.
        readme_hits = detect_frameworks(
            tags=agent.tags, tagline=agent.tagline, readme=readme
        )
        m.frameworks = sorted(set(m.frameworks) | set(readme_hits))


def _stalest_entries(paths: list[Path], n: int) -> list[Path]:
    """Sort by last_refreshed_at ascending and take the first n."""
    def key(p: Path) -> str:
        try:
            return json.loads(p.read_text()).get("last_refreshed_at") or ""
        except Exception:
            return ""
    return sorted(paths, key=key)[:n]


@click.command()
@click.option(
    "--enrich-limit",
    default=500,
    show_default=True,
    help="Max entries to fully enrich (Tier 2) per run. 0 disables enrichment.",
)
@click.option(
    "--skip-runnable",
    is_flag=True,
    help="Skip the runnable rescan pass (just do Tier 2 enrichment).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Compute everything; write nothing.",
)
def main(enrich_limit: int, skip_runnable: bool, dry_run: bool) -> None:
    """Run the weekly rescan + Tier 2 enrichment."""
    budget = budget_from_env()
    set_budget(budget)
    console.print(
        f"[bold]ONEXUS-Agents weekly[/] · enrich_limit={enrich_limit} "
        f"skip_runnable={skip_runnable} dry_run={dry_run}"
    )
    console.print(f"[dim]budget · gh={budget.gh_remaining} hf={budget.hf_remaining}")

    paths = list(iter_catalog_files())
    flips = 0
    enriched = 0
    skipped_budget = 0

    with httpx.Client() as client:
        # Pass 1: runnable rescan (cheap, every entry that isn't already runnable)
        if not skip_runnable:
            for p in paths:
                if not budget.can_spend("gh"):
                    skipped_budget += 1
                    continue
                try:
                    agent = load_agent_file(p)
                except Exception as e:
                    console.print(f"[yellow]skip {p}: {e}")
                    continue
                was_runnable = agent.runnable
                runnable, adapter = _rescan_runnable(client, agent)
                if runnable and not was_runnable:
                    agent.runnable = True
                    agent.adapter_ref = agent.adapter_ref or adapter
                    agent.last_refreshed_at = datetime.now(UTC)
                    if not dry_run:
                        _save(p, agent)
                    flips += 1
                    console.print(f"[green]runnable[/] {agent.category}/{agent.slug}")

        # Pass 2: Tier 2 enrichment on the staleset N entries
        if enrich_limit > 0:
            targets = _stalest_entries(paths, enrich_limit)
            for p in targets:
                if not budget.can_spend("gh"):
                    skipped_budget += 1
                    continue
                try:
                    agent = load_agent_file(p)
                except Exception as e:
                    console.print(f"[yellow]skip {p}: {e}")
                    continue
                _enrich(client, agent)
                agent.last_refreshed_at = datetime.now(UTC)
                if not dry_run:
                    _save(p, agent)
                enriched += 1

    console.print(
        f"[green]Done.[/] runnable_flips={flips} enriched={enriched} "
        f"budget_skipped={skipped_budget}"
    )
    console.print(f"[dim]budget left · gh={budget.gh_remaining} hf={budget.hf_remaining}")


if __name__ == "__main__":
    main()
