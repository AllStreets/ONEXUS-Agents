"""Convert a GitHub Issue (filed via the agent-submission template) into a
validated catalog entry. Run by .github/workflows/submission.yml when an
issue gets the `agent-submission` label.

Strategy:
  1. Parse the issue body — GitHub Issue Forms produce structured H3 headers
     followed by user input.
  2. Reconcile user-provided fields against the real GitHub/HF API metadata
     so we never trust raw user input for stars/license/last_commit_at.
  3. Validate against pipeline.schema.Agent.
  4. Write to catalog/<category>/<slug>.json.

On failure (parse error, repo 404, schema invalid), exit with code 1 and
print a clean message — the workflow surfaces it as an issue comment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import httpx

from pipeline.budget import APIBudget, set_budget
from pipeline.build import build_from_github, build_from_huggingface
from pipeline.paths import CATALOG_DIR
from pipeline.store import load_categories


def _parse_form(body: str) -> dict[str, str]:
    """Pull H3-headed sections from a GitHub issue-form body into a dict.

    GitHub forms render each labeled field as:

        ### Field Label
        <value>

    Multi-line values are preserved up to the next H3 or EOF.
    """
    parts = re.split(r"\n###\s+", "\n" + body.strip())
    out: dict[str, str] = {}
    for p in parts:
        if not p.strip():
            continue
        lines = p.split("\n", 1)
        label = lines[0].strip().lower()
        value = lines[1].strip() if len(lines) > 1 else ""
        # Issue forms write the literal "_No response_" when an optional field
        # is left blank — treat as empty.
        if value.lower() == "_no response_":
            value = ""
        out[label] = value
    return out


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:64] or "agent"


@click.command()
@click.option("--issue-body-file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output-summary-file", required=False, type=click.Path(dir_okay=False))
def main(issue_body_file: str, output_summary_file: str | None) -> None:
    """Process one submission issue body into a catalog entry."""
    body = Path(issue_body_file).read_text()
    fields = _parse_form(body)

    source = fields.get("source", "").strip().lower()
    repo = fields.get("repository (owner/name) or model id", "").strip()
    category = fields.get("category", "").strip().lower()
    tagline_override = fields.get("tagline (optional)", "").strip() or None
    runnable_raw = fields.get("runnable via mcp?", "").strip().lower()

    if not source or not repo or not category:
        sys.exit(f"missing required field. Parsed: source={source!r} repo={repo!r} cat={category!r}")

    cats = load_categories()
    valid_slugs = {c.slug for c in cats.categories}
    if category not in valid_slugs:
        sys.exit(f"invalid category {category!r}. Allowed: {sorted(valid_slugs)}")

    runnable = runnable_raw.startswith("yes")
    adapter_ref = "mcp/stdio" if runnable else None

    # No budget cap needed for a one-off submission — the script makes 1-2 calls.
    set_budget(APIBudget(gh_remaining=100, hf_remaining=100))

    with httpx.Client() as client:
        if source == "github":
            agent = build_from_github(
                client, repo, category,
                runnable=runnable, adapter_ref=adapter_ref,
                notes=tagline_override, discovered_via="submission",
            )
        elif source == "huggingface":
            agent = build_from_huggingface(
                client, repo, category,
                runnable=runnable, adapter_ref=adapter_ref,
                notes=tagline_override, discovered_via="submission",
            )
        else:
            sys.exit(f"unknown source: {source!r}")

    if agent is None:
        sys.exit(f"could not fetch {source} metadata for {repo!r} — repo gone, private, or rate-limited")

    # Slug uniqueness — submissions can't displace an existing seeded/auto entry.
    existing = CATALOG_DIR / category / f"{agent.slug}.json"
    if existing.exists():
        sys.exit(
            f"slug {agent.slug!r} already exists in {category!r}. "
            "Submissions can't displace existing entries; close this issue or pick a unique name."
        )

    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text(agent.model_dump_json(indent=2, exclude_none=False) + "\n")

    summary = (
        f"Created `catalog/{category}/{agent.slug}.json` from submission.\n\n"
        f"- name: **{agent.name}**\n"
        f"- tagline: {agent.tagline}\n"
        f"- license: {agent.license}\n"
        f"- runnable: {agent.runnable}\n"
        f"- discovered_via: {agent.discovered_via}\n\n"
        f"first_seen_at: {agent.first_seen_at.isoformat()}\n"
        f"last_refreshed_at: {agent.last_refreshed_at.isoformat()}\n"
    )
    if output_summary_file:
        Path(output_summary_file).write_text(summary)
    print(summary)


if __name__ == "__main__":
    main()
