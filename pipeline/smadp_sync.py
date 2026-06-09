"""SMADP sync helper — convert ONEXUS-Agents catalog entries to
SMADP-shaped safety-profile seeds.

SMADP maintains `catalog/profiles/_unverified/*.json` — auto-generated
seeds awaiting evidence-cited safety analysis. This script reads the
ONEXUS-Agents catalog, filters to high-signal candidates, and emits
SMADP profile JSON ready to drop into SMADP's _unverified/ dir.

What's a high-signal candidate?
  - runnable=true (MCP adapter exists, so SMADP can actually run it)
  - OR composite_score >= threshold (the agent is at least credible)
  - AND not archived

Mapping:
  ONEXUS-Agents field     → SMADP profile field
  ---------------------------------------------
  slug                    → profile_id
  name                    → display_name
  tagline                 → summary
  source.github           → source_url
  license                 → license
  metrics.frameworks      → frameworks
  metrics.last_commit_at  → last_active
  runnable + adapter_ref  → runtime.mcp_adapter
  category                → primary_category

Fields SMADP needs that ONEXUS-Agents doesn't track (capabilities,
network egress, OAuth scopes, sandboxing model) get null defaults —
they're what the human / sandbox reviewer fills in during safety
analysis. The seed exists so the catalog is queued, not pre-judged.

Run via:

    uv run python -m pipeline.smadp_sync \\
        --catalog /path/to/ONEXUS-Agents \\
        --out /path/to/SMADP/catalog/profiles/_unverified \\
        [--min-score 0.30] [--runnable-only]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.client import OnexusAgentsClient


def to_smadp_profile(agent) -> dict:
    """Convert one Agent to a SMADP _unverified seed profile."""
    return {
        "profile_id": agent.slug,
        "display_name": agent.name,
        "summary": agent.tagline,
        "primary_category": agent.category,
        "source_url": (
            f"https://github.com/{agent.source.github}"
            if agent.source.github
            else (
                f"https://huggingface.co/{agent.source.huggingface}"
                if agent.source.huggingface
                else None
            )
        ),
        "license": agent.license,
        "frameworks": agent.metrics.frameworks or [],
        "last_active": (
            agent.metrics.last_commit_at.isoformat()
            if agent.metrics.last_commit_at
            else None
        ),
        "runtime": {
            "runnable_via_mcp": bool(agent.runnable),
            "mcp_adapter": agent.adapter_ref,
        },
        # Stuff SMADP fills in during safety analysis — null on import.
        "capabilities": None,
        "io_surfaces": None,
        "network_egress": None,
        "oauth_scopes": None,
        "sandboxing": None,
        # Provenance — every seed remembers where it came from.
        "_sourced_from": {
            "system": "ONEXUS-Agents",
            "composite_score": agent.composite_score,
            "rank_in_category": agent.rank_in_category,
            "discovered_via": agent.discovered_via,
            "synced_at": datetime.now(UTC).isoformat(),
        },
        "evidence_level": "docs-only",  # default until SMADP upgrades it
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync catalog to SMADP seeds.")
    parser.add_argument(
        "--catalog",
        required=True,
        help="Path to ONEXUS-Agents clone (the local mode is faster + avoids rate limits).",
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

    written = skipped = 0
    for a in agents:
        if (a.metrics.archived or False):
            skipped += 1
            continue
        profile = to_smadp_profile(a)
        target = out_dir / f"{a.slug}.json"
        if args.dry_run:
            written += 1
            continue
        target.write_text(json.dumps(profile, indent=2) + "\n")
        written += 1

    verb = "would write" if args.dry_run else "wrote"
    print(f"{verb} {written} seeds · skipped {skipped} archived")


if __name__ == "__main__":
    main()
