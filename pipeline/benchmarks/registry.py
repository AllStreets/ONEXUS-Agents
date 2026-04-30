"""Benchmark fetcher registry.

Real scrapers attach themselves here keyed by canonical benchmark name.
For now, the nightly job uses cached scores from seed entries. Each scraper
returns a dict keyed by `<owner>/<repo>` (or HF model id) -> latest score.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

ScraperFn = Callable[[httpx.Client], dict[str, float]]

_REGISTRY: dict[str, ScraperFn] = {}


def register(name: str):
    def decorator(fn: ScraperFn) -> ScraperFn:
        _REGISTRY[name.lower()] = fn
        return fn

    return decorator


def get(name: str) -> ScraperFn | None:
    return _REGISTRY.get(name.lower())


def all_scrapers() -> dict[str, ScraperFn]:
    return dict(_REGISTRY)
