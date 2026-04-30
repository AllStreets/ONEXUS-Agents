"""Composite ranking — popularity + recency + benchmark."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from pipeline.schema import Agent, Category

# Weight schedules
WEIGHTS_BENCH = {
    "benchmark": 0.30,
    "stars": 0.18,
    "downloads": 0.18,
    "recency": 0.14,
    "age": 0.05,
    "runnable": 0.05,
    "reserved": 0.10,
}

WEIGHTS_NO_BENCH = {
    "stars": 0.28,
    "downloads": 0.28,
    "recency": 0.22,
    "age": 0.07,
    "runnable": 0.05,
    "reserved": 0.10,
}

RECENCY_HALF_LIFE_DAYS = 90
AGE_CAP_DAYS = 730  # 24 months


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


def rank_category(agents: list[Agent], category: Category, now: datetime | None = None) -> list[Agent]:
    """Compute composite_score and rank_in_category in-place; return sorted list."""
    if not agents:
        return []
    now = now or datetime.now(UTC)
    has_bench = category.benchmark_anchor is not None
    weights = WEIGHTS_BENCH if has_bench else WEIGHTS_NO_BENCH

    star_norm = log_normalize([a.metrics.stars or 0 for a in agents])
    dl_norm = log_normalize([a.metrics.downloads_30d or 0 for a in agents])

    for i, a in enumerate(agents):
        score = 0.0
        if has_bench:
            bench = benchmark_score(a, category) or 0.0
            score += weights["benchmark"] * bench
        score += weights["stars"] * star_norm.get(i, 0.0)
        score += weights["downloads"] * dl_norm.get(i, 0.0)
        score += weights["recency"] * recency_score(a.metrics.last_commit_at, now)
        score += weights["age"] * age_score(a.metrics.first_commit_at, now)
        score += weights["runnable"] * (1.0 if a.runnable else 0.0)
        # reserved -> 0 for now
        a.composite_score = round(score, 4)

    agents.sort(key=lambda a: a.composite_score, reverse=True)
    for rank, a in enumerate(agents, start=1):
        a.rank_in_category = rank
    return agents
