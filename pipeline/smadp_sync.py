"""SMADP sync helper — convert ONEXUS-Agents catalog entries to
SMADP-shaped safety-profile seeds.

SMADP maintains `catalog/profiles/_unverified/*.json` — auto-generated
seeds awaiting evidence-cited safety analysis. This script reads the
ONEXUS-Agents catalog, filters to high-signal candidates, and emits
profile JSON matching SMADP's existing _unverified schema with the
safety-evaluation fields left empty (so SMADP's analysis pipeline
knows what to fill in).

Schema match: this script targets SMADP's Profile model v1.1
(smadp/schemas/profile.py): vendor is an object, source_type is the
hyphenated enum, verification is the strict 4-field block, and catalog
provenance rides in the top-level `onexus` dict alongside
`evidence_level: "unverified-profile"` and `composite_score` — the exact
fields SMADP's EnrichmentPlanner uses to queue research once a seed is
promoted into catalog/profiles/. Safety-classification fields default to
empty objects/arrays — that's how SMADP's loader recognises "needs
analysis."

What we DO fill in (from catalog metadata, low judgment-call):
  slug, name, tagline, category, homepage (source URL), source_type,
  first_seen_at, last_refreshed_at, vendor, schema_version

What we leave for SMADP's analysis pipeline (high judgment-call):
  capabilities, io_surfaces, concurrency_model, data_classes_touched,
  evidence_refs, pairings, permissions_requested, sandboxing

Run via:

    onexus-agents-smadp-sync \\
        --catalog /path/to/ONEXUS-Agents \\
        --out /path/to/SMADP/catalog/profiles/_unverified \\
        [--min-score 0.30] [--runnable-only] [--skip-existing] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.client import OnexusAgentsClient

SCHEMA_VERSION = "1.1"


def _source_type(agent) -> str:
    """SMADP distinguishes between open-source repos and SaaS products.
    The catalog only tracks open-source by definition — every entry has
    a github or huggingface source — so source_type is always 'open-source'
    (SMADP's SourceType enum is hyphenated)."""
    return "open-source"


def _vendor(agent) -> dict:
    """SMADP's Vendor model: type is company|org|individual. The catalog's
    author.type is user|org — map user to individual."""
    return {
        "type": "org" if agent.author.type == "org" else "individual",
        "handle": agent.author.handle,
        "url": str(agent.author.url),
    }


def _homepage(agent) -> str | None:
    """Best public URL: homepage field if set, else github repo, else HF model page."""
    if agent.source.homepage:
        return str(agent.source.homepage)
    if agent.source.github:
        return f"https://github.com/{agent.source.github}"
    if agent.source.huggingface:
        return f"https://huggingface.co/{agent.source.huggingface}"
    return None


def to_smadp_profile(agent) -> dict:
    """Convert one Agent to a SMADP _unverified seed profile.

    All structural fields SMADP expects are present so its loader
    doesn't choke. Safety-classification fields are empty by design.
    The `verification` block carries provenance back to the catalog so
    the human reviewer can trace + audit the source.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "slug": agent.slug,
        # SMADP enforces max lengths (name 100, tagline 200).
        "name": agent.name[:100],
        "tagline": (agent.tagline or None) and agent.tagline[:200],
        "category": agent.category,
        "vendor": _vendor(agent),
        "homepage": _homepage(agent),
        "repo_url": (
            f"https://github.com/{agent.source.github}" if agent.source.github else None
        ),
        "source_type": _source_type(agent),
        "first_seen_at": (
            agent.first_seen_at.isoformat() if agent.first_seen_at else now
        ),
        "last_refreshed_at": (
            agent.last_refreshed_at.isoformat() if agent.last_refreshed_at else now
        ),
        # Safety-classification fields. SMADP's analysis pipeline fills these.
        # Empty containers (not null) so SMADP's loader knows "structurally valid,
        # just unevaluated" — every subfield has a conservative schema default.
        "capabilities": {},
        "io_surfaces": {},
        "concurrency_model": {},
        "data_classes_touched": [],
        "evidence_refs": [],
        "pairings": [],
        "permissions_requested": {},
        "sandboxing": {},
        # Verification block — strict shape (SMADP forbids extra keys here).
        "verification": {
            "status": "unverified",
            "verified_by": None,
            "verified_at": now,
            "method": "auto-only",
        },
        # Autopilot-pipeline metadata. evidence_level "unverified-profile" +
        # onexus.source_github is exactly what SMADP's EnrichmentPlanner keys
        # on, so a seed promoted out of _unverified/ into catalog/profiles/
        # enters the research queue with no further transformation.
        "evidence_level": "unverified-profile",
        "composite_score": max(0.0, min(1.0, agent.composite_score)),
        "license": agent.license,
        "onexus": {
            "source_github": agent.source.github,
            "source_huggingface": agent.source.huggingface,
            "author_handle": agent.author.handle,
            "tags": agent.tags,
            "runnable": bool(agent.runnable),
            "mcp_adapter": agent.adapter_ref,
            "rank_in_category": agent.rank_in_category,
            "discovered_via": agent.discovered_via,
            "frameworks_detected": agent.metrics.frameworks or [],
            "source_catalog_url": (
                f"https://onexus-agents.vercel.app/catalog/{agent.category}/{agent.slug}"
            ),
            "sourced_from": "ONEXUS-Agents",
            "synced_at": now,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync catalog to SMADP _unverified seeds.")
    parser.add_argument(
        "--catalog",
        required=True,
        help="Path to ONEXUS-Agents clone (local mode is faster + avoids rate limits).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Where to write seed profiles (SMADP's catalog/profiles/_unverified).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.30,
        help="Composite score floor for non-runnable candidates (default 0.30).",
    )
    parser.add_argument(
        "--runnable-only",
        action="store_true",
        help="Only emit seeds for runnable=true agents.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Don't overwrite seeds that already exist (default: overwrite to refresh provenance).",
    )
    parser.add_argument(
        "--skip-existing-in",
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "Also skip slugs that already have a profile anywhere under DIR "
            "(recursive; repeatable). Point this at SMADP's catalog/profiles "
            "so seeds are only written for agents SMADP has never seen — "
            "slugs already imported (e.g. by bootstrap-onexus) would "
            "otherwise collide and fail smadp lint's duplicate check."
        ),
    )
    parser.add_argument(
        "--max-new",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Write at most N new seeds this run (volume cap for unattended "
            "nightly syncs). Deferred candidates are counted and reported, "
            "not silently dropped; they remain eligible next run."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts; write nothing.",
    )
    args = parser.parse_args()

    client = OnexusAgentsClient.from_local(args.catalog)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    known_slugs: set[str] = set()
    for d in args.skip_existing_in:
        known_slugs.update(p.stem for p in Path(d).rglob("*.json"))

    if args.runnable_only:
        agents = client.runnable_only()
    else:
        agents = [
            a
            for a in client.list_agents()
            if a.runnable or a.composite_score >= args.min_score
        ]

    written = skipped_archived = skipped_existing = skipped_known = deferred = 0
    seen_this_run: set[str] = set()
    for a in agents:
        if a.metrics.archived or False:
            skipped_archived += 1
            continue
        if a.slug in known_slugs:
            skipped_known += 1
            continue
        target = out_dir / f"{a.slug}.json"
        if a.slug in seen_this_run or (args.skip_existing and target.exists()):
            skipped_existing += 1
            continue
        if args.max_new is not None and written >= args.max_new:
            deferred += 1
            continue
        seen_this_run.add(a.slug)
        profile = to_smadp_profile(a)
        if args.dry_run:
            written += 1
            continue
        target.write_text(json.dumps(profile, indent=2) + "\n")
        written += 1

    verb = "would write" if args.dry_run else "wrote"
    parts = [f"{verb} {written} seeds", f"skipped {skipped_archived} archived"]
    if args.skip_existing:
        parts.append(f"skipped {skipped_existing} existing")
    if args.skip_existing_in:
        parts.append(f"skipped {skipped_known} already known to SMADP")
    if deferred:
        parts.append(f"deferred {deferred} past --max-new cap (eligible next run)")
    print(" · ".join(parts))


if __name__ == "__main__":
    main()
