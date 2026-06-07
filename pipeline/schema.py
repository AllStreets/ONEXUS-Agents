"""Pydantic models matching catalog/<cat>/<agent>.json."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Author(BaseModel):
    type: Literal["user", "org"]
    handle: str
    url: HttpUrl


class Source(BaseModel):
    primary: Literal["github", "huggingface"]
    github: str | None = None
    huggingface: str | None = None
    homepage: HttpUrl | None = None


class Metrics(BaseModel):
    stars: int | None = None
    downloads_30d: int | None = None
    last_commit_at: datetime | None = None
    first_commit_at: datetime | None = None
    # Tier 1: fields already returned by /repos and /models — no new API cost.
    forks: int | None = None
    watchers: int | None = None
    open_issues: int | None = None
    archived: bool | None = None
    is_fork: bool | None = None
    is_template: bool | None = None
    library_name: str | None = None
    pipeline_tag: str | None = None
    # Tier 2: one extra cheap API call each. Captured by the weekly enricher.
    contributors_count: int | None = None
    releases_total: int | None = None
    latest_release_at: datetime | None = None
    commits_90d: int | None = None
    has_ci: bool | None = None
    readme_length: int | None = None
    # Tier 3: derived from tags/tagline/README — no extra API call.
    # Slugs of detected agent frameworks (langchain, crewai, etc.). Populated
    # at build time from topics/tags + tagline, enriched during weekly rescan
    # via README pattern matching.
    frameworks: list[str] = Field(default_factory=list)


class Benchmark(BaseModel):
    name: str
    score: float
    as_of: str
    source_url: HttpUrl


class Agent(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    name: str
    tagline: str
    category: str
    tags: list[str] = Field(default_factory=list)
    author: Author
    source: Source
    license: str
    metrics: Metrics
    benchmarks: list[Benchmark] = Field(default_factory=list)
    runnable: bool = False
    adapter_ref: str | None = None
    composite_score: float = 0.0
    rank_in_category: int = 999
    discovered_via: Literal["seed", "auto", "submission"]
    first_seen_at: datetime
    last_refreshed_at: datetime


class CategoryAnchor(BaseModel):
    name: str
    leaderboard_url: HttpUrl
    weight_share: float


class Category(BaseModel):
    slug: str
    name: str
    description: str
    benchmark_anchor: CategoryAnchor | None = None
    seed_keywords: list[str] = Field(default_factory=list)
    github_search_queries: list[str] = Field(default_factory=list)
    huggingface_filters: dict = Field(default_factory=dict)


class CategoryIndex(BaseModel):
    version: int
    updated_at: str
    categories: list[Category]
