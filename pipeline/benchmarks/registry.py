"""Benchmark scraper registry.

Scrapers register themselves on import via the BenchmarkScraper subclass
hook in base.py. The nightly imports pipeline.benchmarks (which imports
every concrete scraper module), so by the time `all_scrapers()` is called
the registry is fully populated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.benchmarks.base import BenchmarkScraper

_REGISTRY: dict[str, type[BenchmarkScraper]] = {}


def register_class(cls: type[BenchmarkScraper]) -> None:
    """Called from BenchmarkScraper.__init_subclass__."""
    if not getattr(cls, "name", None):
        return
    _REGISTRY[cls.name.lower()] = cls


def get(name: str) -> type[BenchmarkScraper] | None:
    return _REGISTRY.get(name.lower())


def all_scrapers() -> list[type[BenchmarkScraper]]:
    return list(_REGISTRY.values())
