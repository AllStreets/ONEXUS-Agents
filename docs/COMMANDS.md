# Command cheatsheet

Every terminal command and dev-server keyboard shortcut you'd reach for in this
repo. Lives in `docs/` so it doesn't crowd the GitHub homepage. Treat this as
the source of truth — if a command falls out of date here, fix it here first.

---

## One-time setup

| Goal | Command |
|---|---|
| Fresh Mac, full bootstrap (brew, python, node, pnpm, gh, deps, smoke test) | `./docs/setup-new-mac.sh` |
| Create the pipeline venv from scratch | `uv venv && source .venv/bin/activate` |
| Install pipeline + dev deps | `uv pip install -e ".[dev]"` |
| Resync after a folder move or stale shebangs | `uv sync` |
| Install site deps | `cd site && pnpm install` |

The repo ships three pip extras on `onexus-agents-pipeline`:

```bash
pip install "onexus-agents-pipeline[dev]"      # pytest + ruff (local dev)
pip install "onexus-agents-pipeline[client]"   # typed Python client (httpx, pydantic)
pip install "onexus-agents-pipeline[mcp]"      # MCP server wrapper
```

---

## Pipeline CLIs

All installed by the editable install above. Each has its own `--help`.

| Command | What it does |
|---|---|
| `onexus-agents-validate` | Schema-validate the **entire** catalog (exits non-zero on any failure) |
| `onexus-agents-validate catalog/<cat>/<slug>.json` | Validate one file |
| `onexus-agents-nightly --dry-run` | Run the 13:00 UTC pipeline locally, no commits, no PR |
| `onexus-agents-weekly --dry-run` | Run the 17:00 UTC Sunday rescan locally |
| `onexus-agents-submit` | Process a single issue-based submission (the workflow's entry point) |
| `onexus-agents-smadp-sync` | Sync runnable catalog entries into SMADP's profile dir |
| `onexus-agents-mcp --url https://onexus-agents.vercel.app` | Run the MCP server against the live site |
| `onexus-agents-mcp --local /path/to/ONEXUS-Agents` | Run the MCP server against a local clone |

Common flags worth knowing:

- `--dry-run` — compute everything, write nothing. Both `nightly` and `weekly` accept it.
- `nightly --seeds-only` — skip auto-discovery, refresh seeds only.
- `nightly --per-query-limit N` — results per search query. Default 30.
- `nightly --categories <slug>` — limit to one or more category slugs (repeatable).
- `weekly --enrich-limit N` — cap the Tier 2 enrichment pass. Default 500. `0` disables.
- `weekly --skip-runnable` — skip the runnable rescan pass, do Tier 2 only.

---

## Site (Astro)

From `site/`:

| Command | What it does |
|---|---|
| `pnpm dev` | Start the Astro dev server (default port `4321`, picks the next free) |
| `pnpm build` | Static build into `site/dist/` |
| `pnpm preview` | Serve the built output for a smoke test |
| `pnpm check` | `astro check` — type-check `.astro` + TypeScript |
| `pnpm astro <subcommand>` | Pass through to Astro CLI (e.g. `pnpm astro add tailwind`) |

### Dev-server keyboard shortcuts

While `pnpm dev` is running in the terminal, press the letter then Enter:

| Key | Action |
|---|---|
| `r` | Restart the server |
| `u` | Show the server URL |
| `o` | Open the URL in your default browser |
| `c` | Clear the console |
| `q` | Quit |
| `h` | Show this menu in-terminal |

(These come from Vite, which Astro builds on. Same set across Vite 4 / 5 / 6.)

---

## Integration with downstream projects

From the Integration workspace (`~/Downloads/Integration/`), both scripts are
idempotent and prompt before any irreversible step. Defaults point at sibling
folders here — env-var overrides are no longer required from the canonical
layout (set by PR #101).

| Command | What it does |
|---|---|
| `bash docs/integrate/smadp.sh` | Install `[client]` into SMADP's uv venv + dry-run sync → real sync into `_unverified/` |
| `bash docs/integrate/nexus.sh` | Install `[client]` + `[mcp]` into NEXUS's pip venv + print the `tools.py` patch |
| `SMADP_REPO=... bash docs/integrate/smadp.sh` | Override target SMADP location |
| `NEXUS_REPO=... bash docs/integrate/nexus.sh` | Override target NEXUS location |
| `ONEXUS_AGENTS_REPO=... bash docs/integrate/smadp.sh` | Override which catalog clone the sync reads |

Recovery:

```bash
# SMADP undo (sync only writes into _unverified/)
cd ~/Downloads/Integration/SMADP && git restore catalog/profiles/_unverified/

# NEXUS undo (revert the manual tools.py paste, uninstall the package)
pip uninstall onexus-agents-pipeline
cd ~/Downloads/Integration/NEXUS && git restore nexus/mcp/tools.py
```

---

## Catalog day-to-day

| Goal | Command |
|---|---|
| Count agents in a category | `ls catalog/<cat>/ \| wc -l` |
| Count runnable entries | `grep -l '"runnable": true' catalog/**/*.json \| wc -l` |
| Find entries with a specific framework | `grep -l '"frameworks":.*"mcp"' catalog/**/*.json` |
| Inspect the categories registry | `jq '.categories[] \| select(.benchmark_anchor) \| .slug + " → " + .benchmark_anchor.name' catalog/_categories.json` |
| Eyeball today's dropped slugs | `cat catalog/_dropped/$(date -u +%Y-%m-%d).json \| jq .` |

---

## Git workflow (PR with auto-merge)

The repo uses squash-merge with auto-merge — open the PR and immediately enable
auto-merge so it lands the moment checks go green:

```bash
git checkout -b <type>/<short-slug>
git add <files> && git commit -m "<type>(<scope>): <one-liner>"
git push -u origin <branch>

gh pr create --title "..." --body "..."
PR=$(gh pr view --json number --jq .number)

# Poll until checks register, then enable auto-merge
for i in $(seq 1 24); do
  STATE=$(gh pr view "$PR" --json mergeStateStatus --jq '.mergeStateStatus')
  [ "$STATE" != "UNKNOWN" ] && break
  sleep 5
done
gh pr merge "$PR" --squash --auto --delete-branch
```

Conventional commit prefixes used in `git log`:

- `feat(<scope>)` — user-visible new functionality
- `fix(<scope>)` — bug fix
- `chore(<scope>)` — non-code, non-doc tooling (deps, settings)
- `docs(<scope>)` — README / docs only
- `refactor(<scope>)` — code reshape, no behavior change

---

## Python client (programmatic use)

```python
from pipeline.client import OnexusAgentsClient

c = OnexusAgentsClient.from_url()                 # → onexus-agents.vercel.app
# c = OnexusAgentsClient.from_local("/path/to/ONEXUS-Agents")

c.runnable_only()                                 # every runnable: true entry, sorted by composite_score
c.list_agents(category="coding")                  # filter; combinable with runnable=, framework=, benchmarked=
c.list_agents(framework="mcp", runnable=True)     # filters AND together
c.get_agent("coding", "aider")                    # Agent | None — needs both category and slug
c.search("browser", limit=20)                     # keyword search across name/tags/category
c.categories()                                    # list[str] of all category slugs
c.by_framework("langchain")                       # shorthand for list_agents(framework=...)
```

The `Agent` model mirrors `catalog/<cat>/<slug>.json` 1:1 — same field names,
typed via Pydantic.

---

## MCP server (NEXUS uses these)

When wired into NEXUS via the `nexus_agents_*` tools, the server exposes:

| Tool | Purpose |
|---|---|
| `nexus_agents_browse` | List by category, filter to runnable |
| `nexus_agents_search` | Keyword search across name/tags/category |
| `nexus_agents_info` | Full metadata + MCP adapter descriptor for a slug |

Standalone for testing:

```bash
onexus-agents-mcp --url https://onexus-agents.vercel.app
# or
python -m pipeline.mcp_server --local .
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `bad interpreter: .../bin/python3: no such file or directory` | `uv sync` — venv was moved, rewrites shebangs |
| `Port 4321 is in use` on `pnpm dev` | Stale astro process. `pkill -f "astro dev"` then re-run |
| MCP server can't reach the catalog | Default URL is `onexus-agents.vercel.app`; pass `--local <path>` for offline use |
| `onexus-agents-nightly` hits API budget | Set `GH_PAT` for 30k GH calls (vs 12k free-tier default) |
| Catalog validation fails after a hand edit | `onexus-agents-validate catalog/<cat>/<slug>.json` to see the specific field error |
