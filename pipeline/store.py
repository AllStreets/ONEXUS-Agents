"""Catalog and seed I/O."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import yaml

from pipeline.paths import CATALOG_DIR, CATEGORIES_FILE, SEEDS_DIR
from pipeline.schema import Agent, CategoryIndex


def load_categories() -> CategoryIndex:
    raw = json.loads(CATEGORIES_FILE.read_text())
    return CategoryIndex.model_validate(raw)


def load_seeds(category_slug: str) -> list[dict]:
    f = SEEDS_DIR / f"{category_slug}.yaml"
    if not f.exists():
        return []
    data = yaml.safe_load(f.read_text())
    return list(data.get("agents", []))


def iter_catalog_files() -> Iterator[Path]:
    if not CATALOG_DIR.exists():
        return
    for cat_dir in sorted(CATALOG_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue
        for f in sorted(cat_dir.glob("*.json")):
            yield f


def load_agent_file(path: Path) -> Agent:
    return Agent.model_validate_json(path.read_text())


def write_agent(agent: Agent) -> Path:
    out_dir = CATALOG_DIR / agent.category
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{agent.slug}.json"
    out.write_text(
        agent.model_dump_json(indent=2, exclude_none=False) + "\n",
    )
    return out


def category_dir(slug: str) -> Path:
    return CATALOG_DIR / slug
