# Contributing to ONEXUS-Agents

Two ways to contribute: **add an agent** (the common case) or **work on the platform**.

## Add an agent

The catalog is git. Adding an agent is opening a PR.

1. Fork [`AllStreets/ONEXUS-Agents`](https://github.com/AllStreets/ONEXUS-Agents).
2. Create `catalog/<category>/<your-slug>.json` matching the schema in [`README.md`](README.md).
3. Run `onexus-agents-validate catalog/<category>/<your-slug>.json` locally.
4. Open a PR using the **Agent submission** template.

Categories live in [`catalog/_categories.json`](catalog/_categories.json). If your agent
doesn't fit any of the 40, open an issue first — we add categories carefully.

The daily job re-scores everything; you don't need to compute `composite_score`
or `rank_in_category` yourself. Set them to `0.0` and `999`; the job overwrites them.

### If your agent is runnable

Add an MCP adapter under `adapters/<your-slug>/` with:

- `mcp.json` — see [`adapters/README.md`](adapters/README.md) for the full shape.
- `README.md` — one-line install + one-line invocation.

Then set `"runnable": true` and `"adapter_ref": "adapters/<your-slug>/mcp.json"`
on the catalog entry.

## Work on the platform

```sh
# Pipeline
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
ruff check pipeline validator
onexus-agents-nightly --dry-run --seeds-only --categories coding

# Site
cd site
pnpm install
pnpm dev   # http://localhost:4321
pnpm check # astro typecheck
pnpm build
```

### Style

- Python: ruff config in `pyproject.toml`, `target-version = "py312"`.
- TypeScript / Astro: Astro strict mode is on.
- No emoji anywhere — UI uses Lucide-style SVG via `<Icon name="..." />`.

## Takedowns

Maintainers can request removal by opening a [takedown issue](.github/ISSUE_TEMPLATE/takedown.md).
We honor takedown requests within 24 hours.

## License

Apache-2.0. By contributing you agree your contributions are licensed under the same.
