"""Daily quality summary report.

Written at end of nightly to `reports/YYYY-MM-DD.md` and committed
alongside the catalog refresh PR. Surfaces:

- Totals: agents, runnable count, framework coverage, classifier health
- Top movers: which categories grew or shrank
- Pipeline health: budget consumption, classifier ok/err
- Tail tier population per category

Deltas are computed against the on-disk catalog state at call time (which
is "yesterday" if write_report is invoked before _write_and_truncate
rewrites the catalog).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pipeline.paths import CATALOG_DIR
from pipeline.schema import Agent

REPORTS_DIR = CATALOG_DIR.parent / "reports"


def _count_runnable(agents: list[Agent]) -> int:
    return sum(1 for a in agents if a.runnable)


def _count_with_frameworks(agents: list[Agent]) -> int:
    return sum(1 for a in agents if a.metrics.frameworks)


def _framework_histogram(agents: list[Agent]) -> Counter[str]:
    c: Counter[str] = Counter()
    for a in agents:
        for fw in a.metrics.frameworks:
            c[fw] += 1
    return c


def _category_counts(agents: list[Agent]) -> dict[str, int]:
    out: Counter[str] = Counter()
    for a in agents:
        out[a.category] += 1
    return dict(out)


def _format_delta(new: int, old: int) -> str:
    diff = new - old
    if diff == 0:
        return ""
    return f" ({'+' if diff > 0 else ''}{diff})"


def _tail_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    if not CATALOG_DIR.exists():
        return out
    for cat_dir in CATALOG_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue
        tail_dir = cat_dir / "_tail"
        if not tail_dir.exists():
            continue
        n = sum(1 for _ in tail_dir.glob("*.json"))
        if n:
            out[cat_dir.name] = n
    return out


def write_report(
    new_agents: list[Agent],
    prev_agents: list[Agent],
    stats: dict[str, int],
    *,
    cap_per_cat: int,
) -> Path:
    """Write today's report and return its path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out = REPORTS_DIR / f"{today}.md"

    new_total = len(new_agents)
    prev_total = len(prev_agents)
    new_runnable = _count_runnable(new_agents)
    prev_runnable = _count_runnable(prev_agents)
    new_fw_count = _count_with_frameworks(new_agents)
    fw_coverage_pct = 100 * new_fw_count / new_total if new_total else 0

    new_cats = _category_counts(new_agents)
    prev_cats = _category_counts(prev_agents)
    all_cats = sorted(set(new_cats) | set(prev_cats), key=lambda c: -new_cats.get(c, 0))

    cats_at_cap = sorted(c for c in new_cats if new_cats[c] >= cap_per_cat)

    fw_hist = _framework_histogram(new_agents).most_common()
    tail = _tail_counts()
    tail_total = sum(tail.values())

    lines: list[str] = [
        f"# Catalog Report — {today}",
        "",
        "## Totals",
        f"- Agents: **{new_total:,}**{_format_delta(new_total, prev_total)}",
        f"- Categories: **{len(new_cats)}** populated",
        f"- Runnable: **{new_runnable}** ({100 * new_runnable / new_total:.1f}%)" + _format_delta(new_runnable, prev_runnable),
        f"- Framework coverage: **{new_fw_count}** / {new_total} ({fw_coverage_pct:.1f}%)",
        f"- Tail tier: **{tail_total}** entries across {len(tail)} categories",
        "",
        "## Per-category counts",
        "| Category | Today | Δ |",
        "|---|---:|---:|",
    ]
    for cat in all_cats:
        n = new_cats.get(cat, 0)
        d = n - prev_cats.get(cat, 0)
        marker = " (at cap)" if n >= cap_per_cat else ""
        delta = f"{'+' if d > 0 else ''}{d}" if d else "—"
        lines.append(f"| `{cat}`{marker} | {n} | {delta} |")

    at_risk = sum(
        1 for a in new_agents if (a.consecutive_refresh_failures or 0) >= 14
    )
    lines += [
        "",
        "## Pipeline health",
        f"- Classifier OpenAI: ok=**{stats.get('classifier_ok', 0)}** err={stats.get('classifier_err', 0)} capped={stats.get('classifier_capped', 0)}",
        f"- GH API budget remaining: **{stats.get('budget_remaining_gh', 0):,}**",
        f"- HF API budget remaining: **{stats.get('budget_remaining_hf', 0):,}**",
        f"- Categories at cap ({cap_per_cat}): **{len(cats_at_cap)}** — " + (", ".join(f"`{c}`" for c in cats_at_cap) or "none"),
        f"- Stale entries dropped this run: **{stats.get('stale_dropped', 0)}**",
        f"- Stale entries at risk (≥14 consecutive failures): **{at_risk}**",
        "",
    ]

    if fw_hist:
        lines += [
            "## Frameworks detected",
            "| Framework | Count |",
            "|---|---:|",
        ]
        for fw, count in fw_hist:
            lines.append(f"| `{fw}` | {count} |")
        lines.append("")

    if tail:
        lines += [
            "## Tail tier",
            "| Category | Tail count |",
            "|---|---:|",
        ]
        for cat, count in sorted(tail.items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{cat}` | {count} |")
        lines.append("")

    lines.append(f"---\n*generated {datetime.now(UTC).isoformat()}*\n")
    out.write_text("\n".join(lines))
    return out
