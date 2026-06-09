"""SMADP sync helper — convert ONEXUS-Agents catalog entries to
SMADP-shaped safety-profile seeds.

SMADP maintains `catalog/profiles/_unverified/*.json` — auto-generated
seeds awaiting evidence-cited safety analysis. This script reads the
ONEXUS-Agents catalog, filters to high-signal candidates, and emits
profile JSON matching SMADP's existing _unverified schema with the
safety-evaluation fields left empty (so SMADP's analysis pipeline
knows what to fill in).

Schema match: this script targets SMADP's actual seed shape (slug, name,
tagline, category, capabilities, io_surfaces, concurrency_model,
data_classes_touched, evidence_refs, pairings, permissions_requested,
sandboxing, verification, schema_version). Safety-classification fields
default to empty objects/arrays — that's how SMADP's loader recognises
"needs analysis."

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

SCHEMA_VERSION = "1.0"


def _source_type(agent) -> str:
    """SMADP distinguishes between open-source repos and SaaS products.
    The catalog only tracks open-source by definition — every entry has
    a github or huggingface source — so source_type is always 'open_source'."""
    return "open_source"


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
        "name": agent.name,
        "tagline": agent.tagline,
        "category": agent.category,
        "vendor": agent.author.handle,
        "homepage": _homepage(agent),
        "source_type": _source_type(agent),
        "first_seen_at": (
            agent.first_seen_at.isoformat() if agent.first_seen_at else now
        ),
        "last_refreshed_at": (
            agent.last_refreshed_at.isoformat() if agent.last_refreshed_at else now
        ),
        # Safety-classification fields. SMADP's analysis pipeline fills these.
        # Empty containers (not null) so SMADP's loader knows "structurally valid,
        # just unevaluated."
        "capabilities": {},
        "io_surfaces": {},
        "concurrency_model": {},
        "data_classes_touched": [],
        "evidence_refs": [],
        "pairings": [],
        "permissions_requested": {},
        "sandboxing": {},
        # Verification block — provenance + status.
        "verification": {
            "evidence_level": "pending",
            "sourced_from": "ONEXUS-Agents",
            "source_catalog_url": (
                f"https://onexus-agents.vercel.app/catalog/{agent.category}/{agent.slug}"
            ),
            "composite_score": agent.composite_score,
            "rank_in_category": agent.rank_in_category,
            "discovered_via": agent.discovered_via,
            "runnable_via_mcp": bool(agent.runnable),
            "mcp_adapter": agent.adapter_ref,
            "frameworks_detected": agent.metrics.frameworks or [],
            "license": agent.license,
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
        "--dry-run",
        action="store_true",
        help="Print counts; write nothing.",
    )
    args = parser.parse_args()

    client = OnexusAgentsClient.from_local(args.catalog)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.runnable_only:
        agents = client.runnable_only()
    else:
        agents = [
            a
            for a in client.list_agents()
            if a.runnable or a.composite_score >= args.min_score
        ]

    written = skipped_archived = skipped_existing = 0
    for a in agents:
        if a.metrics.archived or False:
            skipped_archived += 1
            continue
        target = out_dir / f"{a.slug}.json"
        if args.skip_existing and target.exists():
            skipped_existing += 1
            continue
        profile = to_smadp_profile(a)
        if args.dry_run:
            written += 1
            continue
        target.write_text(json.dumps(profile, indent=2) + "\n")
        written += 1

    verb = "would write" if args.dry_run else "wrote"
    print(
        f"{verb} {written} seeds · skipped {skipped_archived} archived"
        + (f" · skipped {skipped_existing} existing" if args.skip_existing else "")
    )


if __name__ == "__main__":
    main()
