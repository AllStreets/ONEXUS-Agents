"""onexus-agents-recipes: resolve recipes for catalog agents, then verify them.

    onexus-agents-recipes resolve [--slug S] [--limit N]
    onexus-agents-recipes verify  [--slug S] [--limit N] [--jobs J] [--again]
    onexus-agents-recipes summary

`resolve` reads runnable catalog entries, fetches their evidence at the repo's current
commit and writes recipes/<slug>.json, keeping an existing verification when the install
didn't change. Entries with no recipe go to recipes/_unresolved.json with the reason.
`verify` builds and handshakes recipes that haven't been verified (or all, with --again).
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
import httpx

from pipeline.crawlers import github as gh
from pipeline.paths import CATALOG_DIR, ROOT
from pipeline.recipes.fetch import LiveRegistry, evidence
from pipeline.recipes.resolve import NoRecipe, resolve
from pipeline.recipes.schema import Recipe

RECIPES_DIR = ROOT / "recipes"
UNRESOLVED = RECIPES_DIR / "_unresolved.json"
SUMMARY = RECIPES_DIR / "_summary.json"


def recipe_path(slug: str) -> Path:
    return RECIPES_DIR / f"{slug}.json"


def load(slug: str) -> Recipe | None:
    p = recipe_path(slug)
    return Recipe.model_validate_json(p.read_text()) if p.exists() else None


def save(r: Recipe) -> None:
    RECIPES_DIR.mkdir(exist_ok=True)
    recipe_path(r.slug).write_text(r.model_dump_json(indent=2, exclude_none=True) + "\n")


def _same_install(a: Recipe, b: Recipe) -> bool:
    return (a.install.model_dump(exclude={"digest"}), a.command, a.args) == (
        b.install.model_dump(exclude={"digest"}), b.command, b.args)


def _candidates(slug: str | None) -> list[tuple[str, str, str]]:
    seen, out = set(), []
    for f in sorted(CATALOG_DIR.glob("*/*.json")):
        d = json.loads(f.read_text())
        repo = (d.get("source") or {}).get("github")
        if not d.get("runnable") or not repo or d["slug"] in seen:
            continue
        if slug and d["slug"] != slug:
            continue
        seen.add(d["slug"])
        out.append((d["slug"], repo, d.get("license") or "Unknown"))
    return out


@click.group()
def main() -> None:
    """Recipes that install catalog agents as confined MCP servers."""


@main.command("resolve")
@click.option("--slug")
@click.option("--limit", type=int)
def resolve_cmd(slug: str | None, limit: int | None) -> None:
    todo = _candidates(slug)[:limit] if limit else _candidates(slug)
    unresolved = json.loads(UNRESOLVED.read_text()) if UNRESOLVED.exists() else {}
    made = 0
    with httpx.Client(event_hooks={"response": [gh.auth_fallback_hook]}, follow_redirects=True) as client:
        reg = LiveRegistry(client)
        for i, (s, repo, lic) in enumerate(todo, 1):
            ev = evidence(client, s, repo, lic)
            if not ev:
                unresolved[s] = {"repo": repo, "reason": "repository could not be read"}
                continue
            out = resolve(ev, reg)
            if isinstance(out, NoRecipe):
                unresolved[s] = {"repo": repo, "reason": out.reason}
                if recipe_path(s).exists():
                    recipe_path(s).unlink()
                continue
            prior = load(s)
            if prior and _same_install(prior, out):
                out.verified, out.hosts, out.dockerfile, out.prebuilt = prior.verified, prior.hosts, prior.dockerfile, prior.prebuilt
                out.install.digest = prior.install.digest
            save(out)
            unresolved.pop(s, None)
            made += 1
            if i % 25 == 0:
                click.echo(f"{i}/{len(todo)} read, {made} recipes")
    RECIPES_DIR.mkdir(exist_ok=True)
    UNRESOLVED.write_text(json.dumps(dict(sorted(unresolved.items())), indent=2) + "\n")
    click.echo(f"{len(todo)} entries read: {made} recipes, {len(todo) - made} without one")
    _write_summary()


@main.command("verify")
@click.option("--slug")
@click.option("--limit", type=int)
@click.option("--jobs", type=int, default=2, show_default=True)
@click.option("--again", is_flag=True, help="Re-verify recipes that already have a result.")
def verify_cmd(slug: str | None, limit: int | None, jobs: int, again: bool) -> None:
    from pipeline.recipes.verify import verify

    recipes = [Recipe.model_validate_json(p.read_text()) for p in sorted(RECIPES_DIR.glob("[!_]*.json"))]
    todo = [r for r in recipes if (not slug or r.slug == slug) and (again or r.verified is None)]
    if limit:
        todo = todo[:limit]
    ok = 0
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = {pool.submit(verify, r): r.slug for r in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                r = fut.result()
            except Exception as exc:  # a broken recipe must not stop the run
                click.echo(f"{futures[fut]}: verifier error {exc}")
                continue
            save(r)
            ok += bool(r.verified and r.verified.ok)
            v = r.verified
            click.echo(f"[{n}/{len(todo)}] {r.slug}: " + (f"ok, {len(v.tools)} tools" if v.ok else f"failed at {v.stage}: {v.reason[:120]}"))
    click.echo(f"{len(todo)} verified: {ok} installable")
    _write_summary()


@main.command("summary")
def summary_cmd() -> None:
    click.echo(json.dumps(_write_summary(), indent=2))


def _write_summary() -> dict:
    recipes = [Recipe.model_validate_json(p.read_text()) for p in sorted(RECIPES_DIR.glob("[!_]*.json"))]
    unresolved = json.loads(UNRESOLVED.read_text()) if UNRESOLVED.exists() else {}
    by_kind: dict[str, int] = {}
    failed: dict[str, int] = {}
    for r in recipes:
        by_kind[r.install.kind] = by_kind.get(r.install.kind, 0) + 1
        if r.verified and not r.verified.ok:
            failed[r.verified.stage] = failed.get(r.verified.stage, 0) + 1
    out = {
        "entries_read": len(recipes) + len(unresolved),
        "recipes": len(recipes),
        "by_kind": by_kind,
        "verified_installable": sum(1 for r in recipes if r.installable),
        "verification_failed": failed,
        "not_verified_yet": sum(1 for r in recipes if r.verified is None),
        "without_recipe": len(unresolved),
    }
    SUMMARY.write_text(json.dumps(out, indent=2) + "\n")
    return out
