"""Composite ranking — popularity + recency + benchmark + quality signals.

Quality signals (Tier 1, captured in PR1) fold archived/is_fork/is_template +
forks count + library/pipeline_tag presence into a 0-1 sub-score that occupies
the slot previously labeled `reserved`. Stars weight is reduced because GH
catalog entries always have `downloads_30d=None`, which historically meant the
28% downloads slot just re-amplified stars — a heavily gamed signal.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from pipeline.schema import Agent, Category, Metrics

# Weight schedules. Sum to 1.0 each.
WEIGHTS_BENCH = {
    "benchmark": 0.30,
    "stars": 0.15,
    "forks": 0.07,
    "downloads": 0.10,
    "recency": 0.13,
    "age": 0.05,
    "runnable": 0.05,
    "quality": 0.15,
}

WEIGHTS_NO_BENCH = {
    "stars": 0.22,
    "forks": 0.10,
    "downloads": 0.15,
    "recency": 0.20,
    "age": 0.05,
    "runnable": 0.05,
    "quality": 0.23,
}

RECENCY_HALF_LIFE_DAYS = 90
AGE_CAP_DAYS = 730  # 24 months

# Multiplicative penalties applied AFTER the weighted score. archived repos
# should never beat a live competitor on otherwise-equal signals.
ARCHIVED_PENALTY = 0.5
TEMPLATE_PENALTY = 0.8


def log_normalize(values: list[float]) -> dict[int, float]:
    """log10-scale, then min-max into [0, 1]. Returns per-index scores."""
    if not values:
        return {}
    logs = [math.log10(max(1.0, v)) for v in values]
    lo, hi = min(logs), max(logs)
    if hi - lo < 1e-9:
        return {i: 0.5 for i in range(len(values))}
    return {i: (logs[i] - lo) / (hi - lo) for i in range(len(values))}


def recency_score(last_commit: datetime | None, now: datetime | None = None) -> float:
    if last_commit is None:
        return 0.0
    now = now or datetime.now(UTC)
    if last_commit.tzinfo is None:
        last_commit = last_commit.replace(tzinfo=UTC)
    days = max(0.0, (now - last_commit).total_seconds() / 86_400)
    return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)


def age_score(first_commit: datetime | None, now: datetime | None = None) -> float:
    if first_commit is None:
        return 0.0
    now = now or datetime.now(UTC)
    if first_commit.tzinfo is None:
        first_commit = first_commit.replace(tzinfo=UTC)
    days = (now - first_commit).total_seconds() / 86_400
    return min(1.0, days / AGE_CAP_DAYS)


def benchmark_score(agent: Agent, category: Category) -> float | None:
    """Match the agent's benchmark to the category's anchor; return a 0-1 score."""
    anchor = category.benchmark_anchor
    if not anchor:
        return None
    for b in agent.benchmarks:
        if b.name.lower() == anchor.name.lower():
            # Most reasoning benchmarks are 0-100; clamp to that.
            return max(0.0, min(1.0, b.score / 100.0))
    return 0.0  # category has a benchmark but this agent didn't report a score


def quality_score(m: Metrics) -> float:
    """Composite 0-1 quality signal from Tier 1 metadata.

    Starts at a neutral 0.5, then nudges up/down based on signal presence.
    A fully-unknown agent stays at 0.5 so the catalog isn't punished for
    pre-Tier-1 entries until weekly enrichment fills them in.
    """
    if m.archived:
        return 0.0  # multiplicative archived penalty also applied at top level
    q = 0.5
    # Semantic identity — HF entries with a library/pipeline tag are real
    # surface-area, not just hosted weights.
    if m.library_name or m.pipeline_tag:
        q += 0.15
    # Active maintenance proxy: any open issues == anyone is filing them.
    # We treat unknown (None) as neutral.
    if m.open_issues is not None and m.open_issues > 0:
        q += 0.10
    # Unmodified forks are usually clones; templates are scaffolding.
    if m.is_fork:
        q -= 0.10
    if m.is_template:
        q -= 0.15
    # Discoverability: subscribers (watchers) is a stronger "I depend on this"
    # signal than stars. Reward modestly to avoid double-counting popularity.
    if m.watchers is not None and m.watchers >= 10:
        q += 0.05
    return max(0.0, min(1.0, q))


def penalty_multiplier(m: Metrics) -> float:
    mult = 1.0
    if m.archived:
        mult *= ARCHIVED_PENALTY
    if m.is_template:
        mult *= TEMPLATE_PENALTY
    return mult


def rank_category(agents: list[Agent], category: Category, now: datetime | None = None) -> list[Agent]:
    """Compute composite_score and rank_in_category in-place; return sorted list."""
    if not agents:
        return []
    now = now or datetime.now(UTC)
    has_bench = category.benchmark_anchor is not None
    weights = WEIGHTS_BENCH if has_bench else WEIGHTS_NO_BENCH

    star_norm = log_normalize([a.metrics.stars or 0 for a in agents])
    fork_norm = log_normalize([a.metrics.forks or 0 for a in agents])
    dl_norm = log_normalize([a.metrics.downloads_30d or 0 for a in agents])

    for i, a in enumerate(agents):
        score = 0.0
        if has_bench:
            bench = benchmark_score(a, category) or 0.0
            score += weights["benchmark"] * bench
        score += weights["stars"] * star_norm.get(i, 0.0)
        score += weights["forks"] * fork_norm.get(i, 0.0)
        score += weights["downloads"] * dl_norm.get(i, 0.0)
        score += weights["recency"] * recency_score(a.metrics.last_commit_at, now)
        score += weights["age"] * age_score(a.metrics.first_commit_at, now)
        score += weights["runnable"] * (1.0 if a.runnable else 0.0)
        score += weights["quality"] * quality_score(a.metrics)
        score *= penalty_multiplier(a.metrics)
        a.composite_score = round(score, 4)

    agents.sort(key=lambda a: a.composite_score, reverse=True)
    for rank, a in enumerate(agents, start=1):
        a.rank_in_category = rank
    return agents
