"""Keep the README's headline numbers equal to the catalog that was just written.

The nightly run calls `update_readme()` after it writes the catalog, so the
counts on GitHub are the same build's counts the site shows. Only the text
between the `counts:` markers and the two count badges are rewritten.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from pipeline.paths import CATALOG_DIR

ROOT = CATALOG_DIR.parent
README = ROOT / "README.md"


def catalog_counts() -> dict[str, int]:
    indexed = mcp = benchmarked = 0
    for f in CATALOG_DIR.glob("*/*.json"):
        if f.name.startswith("_") or f.parent.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        indexed += 1
        mcp += 1 if data.get("runnable") else 0
        benchmarked += 1 if data.get("benchmarks") else 0
    adapters = sum(1 for p in (ROOT / "adapters").glob("*/mcp.json"))
    return {"indexed": indexed, "mcp": mcp, "benchmarked": benchmarked, "adapters": adapters}


def _block(c: dict[str, int], date: str) -> str:
    rows = [
        (c["indexed"], "repos indexed ................ crawled, scored, published as JSON"),
        (c["mcp"], "self-declare an MCP server ... their topics/manifest say so. we did not run them."),
        (c["adapters"], "adapters hand-maintained ..... written and kept working by a person"),
    ]
    lines = "\n".join(f"{n:>7,}   {label}" for n, label in rows)
    return (
        "<!-- counts:start -->\n```\n" + lines + "\n```\n\n"
        f"<sub>Counts from the {date} refresh, written by the same run that built the catalog. "
        "The top two move every night; the bottom one only moves when a person writes an adapter. "
        f"{c['benchmarked']:,} entries currently carry a benchmark score.</sub>\n<!-- counts:end -->"
    )


def render(text: str, c: dict[str, int], date: str) -> str:
    text = re.sub(r"<!-- counts:start -->.*?<!-- counts:end -->", lambda _m: _block(c, date), text, flags=re.S)
    text = re.sub(r"badge/indexed-[0-9%C,]+_repos-", f"badge/indexed-{c['indexed']:,}_repos-".replace(",", "%2C"), text)
    text = re.sub(r"badge/self--declare_MCP-[0-9%C,]+-", f"badge/self--declare_MCP-{c['mcp']:,}-".replace(",", "%2C"), text)
    return text


def update_readme(date: str | None = None) -> bool:
    """Rewrite the counts in README.md. Returns True when anything changed."""
    date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    old = README.read_text()
    new = render(old, catalog_counts(), date)
    if new != old:
        README.write_text(new)
    return new != old
