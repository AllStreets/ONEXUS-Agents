"""Base classes for benchmark scrapers.

Each scraper subclasses BenchmarkScraper and implements .fetch() to return
a dict keyed by the catalog entry's matching key (either `owner/repo` for
github sources OR `<owner>/<model>` for HF sources). Values are
BenchmarkEntry objects with a normalized score in [0, 1], an as_of date,
and a source URL.

The nightly job calls every registered scraper once per run, then walks
the catalog: for every agent, if the scraper's data contains its
source key, the score gets appended/updated in agent.benchmarks.

Adding a new scraper is three steps:
  1. Create pipeline/benchmarks/<benchmark_slug>.py
  2. Subclass BenchmarkScraper, implement .name + .fetch()
  3. Import it from pipeline/benchmarks/__init__.py so the register()
     decorator fires at module load

Failure is always non-fatal: a scraper that raises during fetch logs the
exception and the nightly continues with the rest of the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class BenchmarkEntry:
    score: float  # normalized to [0, 1]
    as_of: str  # ISO-8601 date, e.g. "2026-06-08"
    source_url: str  # link back to the leaderboard for citation


class BenchmarkScraper:
    """Abstract base — subclasses provide .name + .fetch()."""

    name: str  # MUST match CategoryAnchor.name exactly (case-insensitive)

    def fetch(self, client: httpx.Client) -> dict[str, BenchmarkEntry]:
        """Return {matching_key: BenchmarkEntry} for every leaderboard entry.

        matching_key is either `owner/repo` (for entries that map to a
        GitHub repo) or an HF model id (`org/model` or `model`). The
        nightly tries both source.github and source.huggingface, so a
        scraper can populate keys for whichever surface fits the
        benchmark.
        """
        raise NotImplementedError

    def __init_subclass__(cls, **kwargs):
        """Auto-register subclasses with the global scraper registry."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and cls.name and not cls.__name__.startswith("_"):
            from pipeline.benchmarks.registry import register_class
            register_class(cls)
