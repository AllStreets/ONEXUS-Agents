"""Validate one or many catalog/<cat>/<agent>.json files.

Used both locally (`onexus-agents-validate path/to/file.json`) and from CI
(no arguments => validate every changed catalog file).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from pydantic import ValidationError

from pipeline.paths import CATALOG_DIR
from pipeline.schema import Agent
from pipeline.store import load_categories


def _valid_categories() -> set[str]:
    return {c.slug for c in load_categories().categories}


def _validate_one(path: Path, allowed_cats: set[str]) -> list[str]:
    errs: list[str] = []
    if not path.exists():
        return [f"{path}: file does not exist"]
    if path.suffix != ".json":
        return [f"{path}: not a .json file"]
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"{path}: invalid JSON — {e}"]

    try:
        agent = Agent.model_validate(raw)
    except ValidationError as e:
        return [f"{path}: schema invalid — {e.error_count()} issue(s):\n{e}"]

    # Path placement matches category
    expected_dir = CATALOG_DIR / agent.category
    try:
        rel = path.resolve().relative_to(expected_dir.resolve())
        if "/" in str(rel):
            errs.append(f"{path}: must be a flat file under {expected_dir}/")
    except ValueError:
        errs.append(
            f"{path}: placed in '{path.parent.name}' but category is '{agent.category}'"
        )

    # Filename matches slug
    if path.stem != agent.slug:
        errs.append(f"{path}: filename '{path.stem}' must match slug '{agent.slug}'")

    # Category must exist
    if agent.category not in allowed_cats:
        errs.append(
            f"{path}: unknown category '{agent.category}'. "
            f"See catalog/_categories.json for the allowed slugs."
        )

    # Source must point somewhere
    if agent.source.primary == "github" and not agent.source.github:
        errs.append(f"{path}: source.primary=github but source.github is null")
    if agent.source.primary == "huggingface" and not agent.source.huggingface:
        errs.append(f"{path}: source.primary=huggingface but source.huggingface is null")

    # Runnable agents must declare an adapter
    if agent.runnable and not agent.adapter_ref:
        errs.append(f"{path}: runnable=true requires adapter_ref")

    return errs


def _expand(targets: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    if not targets:
        out.extend(p for p in CATALOG_DIR.rglob("*.json") if not p.name.startswith("_"))
        return out
    for t in targets:
        p = Path(t)
        if p.is_dir():
            out.extend(p.rglob("*.json"))
        else:
            out.append(p)
    return out


@click.command()
@click.argument("targets", nargs=-1, type=click.Path(path_type=str))
@click.option("--strict", is_flag=True, help="Exit non-zero on any warning.")
def main(targets: tuple[str, ...], strict: bool) -> None:
    """Validate catalog JSON files. With no arguments, validate everything."""
    paths = _expand(targets)
    if not paths:
        click.echo("nothing to validate", err=True)
        sys.exit(1)

    cats = _valid_categories()
    all_errs: list[str] = []
    for p in paths:
        errs = _validate_one(p, cats)
        if errs:
            all_errs.extend(errs)
        else:
            click.echo(f"ok  {p}")

    if all_errs:
        click.echo("", err=True)
        for e in all_errs:
            click.echo(f"FAIL {e}", err=True)
        click.echo(f"\n{len(all_errs)} error(s) across {len(paths)} file(s)", err=True)
        sys.exit(1)
    elif strict:
        click.echo(f"\nclean ({len(paths)} files)")
    else:
        click.echo(f"\nclean ({len(paths)} files)")


if __name__ == "__main__":
    main()
