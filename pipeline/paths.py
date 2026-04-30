"""Filesystem paths used across the pipeline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"
SEEDS_DIR = ROOT / "seeds"
ADAPTERS_DIR = ROOT / "adapters"
CATEGORIES_FILE = CATALOG_DIR / "_categories.json"
DROPPED_DIR = CATALOG_DIR / "_dropped"
CACHE_DIR = ROOT / ".crawl-cache"
