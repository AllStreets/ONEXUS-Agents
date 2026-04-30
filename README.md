# ONEXUS-Agents

> The largest continuously-updated public catalog of the world's most powerful open-source agents.
> Discovered nightly. Ranked transparently. Bridged into ONEXUS on demand.

`status: bootstrapping`  ·  `license: Apache-2.0`  ·  `python: 3.12`  ·  `node: 20.x`  ·  `update cadence: 13:00 UTC`

---

## What this is

ONEXUS-Agents is the public, open-source arm of [ONEXUS](https://github.com/AllStreets/ONEXUS) — the agentic OS kernel.

ONEXUS itself is a closed-loop runtime: Cortex routes intent, Engram remembers, Pulse schedules, Chronicle audits, Aegis enforces. It is the brain.

**ONEXUS-Agents is the body's reach.** It is the catalog the kernel looks at when it needs an external skill: a coding agent, a browser agent, a legal-research agent, a video-generation pipeline. We crawl GitHub and Hugging Face every night, score every candidate against a transparent composite of popularity, recency, runnability, and (where one exists) a real benchmark, and publish the top 100 agents per category as static JSON.

The catalog is the product. The dashboard is the showcase. The MCP bridge is the on-ramp.

## How it works

```
nightly cron (13:00 UTC)
        │
        ▼
  refresh seeds  ──► auto-discover from GitHub + Hugging Face
        │
        ▼
   classify into one of 40 task categories
        │
        ▼
   score (composite)  ──► truncate to top 100 / category
        │
        ▼
   commit to catalog/  ──► Vercel rebuilds dashboard
```

Every agent in the catalog is a single JSON file under `catalog/<category>/<agent-slug>.json`. No database. The git history *is* the audit log.

A subset of catalogued agents are marked `runnable: true` and have an `adapter_ref` — that's the MCP wrapper ONEXUS uses to actually invoke them. Discovery is broad; runnable is curated.

## The 40 categories

Every category gets a top-100 leaderboard. Eight categories anchor on a real, peer-recognised benchmark that contributes 30% of the composite score; the other 32 score on popularity, recency, age, and runnability alone until a credible benchmark exists.

| # | Category | Benchmark |
|---|---|---|
| 1 | coding | SWE-bench Verified |
| 2 | web-dev | — |
| 3 | data-engineering | — |
| 4 | data-science-ml | — |
| 5 | financial-modeling | — |
| 6 | legal-research | LegalBench |
| 7 | customer-support | — |
| 8 | content-writing | — |
| 9 | image-generation | — |
| 10 | video-generation | — |
| 11 | audio-speech | — |
| 12 | translation | — |
| 13 | search-rag | — |
| 14 | browser-automation | WebArena |
| 15 | desktop-os-automation | OSWorld |
| 16 | document-processing | — |
| 17 | email-scheduling | — |
| 18 | devops-sre | — |
| 19 | security-pentesting | — |
| 20 | bioinformatics | — |
| 21 | scientific-research | — |
| 22 | education-tutoring | — |
| 23 | reasoning-math | MATH |
| 24 | multi-agent-orchestration | GAIA |
| 25 | healthcare | — |
| 26 | travel-planning | — |
| 27 | sales-crm | — |
| 28 | marketing | — |
| 29 | social-media | — |
| 30 | e-commerce | — |
| 31 | real-estate | — |
| 32 | cooking | — |
| 33 | music | — |
| 34 | game-playing | — |
| 35 | robotics | — |
| 36 | knowledge-management | — |
| 37 | pdf-forms | — |
| 38 | spreadsheet-excel | SpreadsheetBench |
| 39 | sql-analytics | BIRD-bench |
| 40 | 3d-cad | — |

As new public benchmarks land, they get wired into [`catalog/_categories.json`](catalog/_categories.json) and the score weights flip on automatically.

## Catalog file format

```json
{
  "slug": "aider",
  "name": "Aider",
  "tagline": "Pair-programming AI in your terminal.",
  "category": "coding",
  "tags": ["cli", "git-aware", "multi-file"],
  "author": { "type": "org", "handle": "Aider-AI", "url": "https://github.com/Aider-AI" },
  "source": {
    "primary": "github",
    "github": "Aider-AI/aider",
    "huggingface": null,
    "homepage": "https://aider.chat"
  },
  "license": "Apache-2.0",
  "metrics": {
    "stars": 28400,
    "downloads_30d": null,
    "last_commit_at": "2026-04-22T14:01:00Z",
    "first_commit_at": "2023-05-09T00:00:00Z"
  },
  "benchmarks": [
    { "name": "SWE-bench Verified", "score": 26.3, "as_of": "2026-03-15", "source_url": "..." }
  ],
  "runnable": true,
  "adapter_ref": "adapters/aider/mcp.json",
  "composite_score": 0.812,
  "rank_in_category": 3,
  "discovered_via": "seed",
  "first_seen_at": "2026-01-12T00:00:00Z",
  "last_refreshed_at": "2026-04-29T00:00:00Z"
}
```

## Submitting an agent

Submissions go through GitHub pull requests. The catalog is a git repository, so the act of adding an agent is the act of opening a PR.

1. Fork the repo.
2. Add `catalog/<category>/<your-agent>.json` matching the schema above.
3. Open a PR using the **Agent submission** template.
4. CI runs `onexus-agents-validate` against your file. If it passes, an admin reviews and merges.

You do *not* need to compute `composite_score` or `rank_in_category` — the nightly job recomputes those for everything in the catalog. Hand-authored entries become first-class members of the ranking pool the next night after merge.

## ONEXUS integration

ONEXUS reads this catalog directly. When a user asks ONEXUS for help with a task, Cortex looks at the relevant category, picks among `runnable: true` candidates by composite score and trust history, and dispatches via the agent's MCP adapter.

The adapter contract is intentionally thin:

```
adapters/<agent>/mcp.json    # MCP server descriptor — command, env, capabilities
adapters/<agent>/README.md   # one-line install, one-line invocation
```

MCP-first, with an escape hatch for agents that don't speak MCP yet (a small Python adapter shim).

## Methodology

The composite score is fully public. With a benchmark anchor:

```
0.30 * benchmark
+ 0.18 * stars (normalized)
+ 0.18 * downloads (normalized)
+ 0.14 * recency (last commit)
+ 0.05 * age (project maturity)
+ 0.05 * runnable
+ 0.10 * reserved (community signal, future)
```

Without a benchmark anchor:

```
0.28 * stars
+ 0.28 * downloads
+ 0.22 * recency
+ 0.07 * age
+ 0.05 * runnable
+ 0.10 * reserved
```

Agents below rank 100 in their category are dropped at the next nightly run and replaced by higher-scoring entrants. Drops are logged in `catalog/_dropped/<date>.json` so the displacement is auditable.

See [`docs/superpowers/specs/2026-04-29-onexus-agents-design.md`](docs/superpowers/specs/2026-04-29-onexus-agents-design.md) for the complete design.

## Layout

```
catalog/         per-category JSON files (the catalog itself)
seeds/           hand-curated YAML seeds per category
adapters/        MCP wrappers for runnable agents
pipeline/        nightly ingestion (Python 3.12)
  crawlers/      GitHub + Hugging Face fetchers
  benchmarks/    benchmark scrapers
validator/       schema + PR validation
site/            Astro 4 + Tailwind v4 dashboard
.github/         workflows + PR templates
docs/            design specs and methodology
```

## Local development

```sh
# Pipeline
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
onexus-agents-validate catalog/coding/aider.json
onexus-agents-nightly --dry-run

# Site
cd site && pnpm install && pnpm dev
```

## License

Apache-2.0. Agent metadata and rankings are publicly redistributable. Each catalogued agent retains its own upstream license — see the `license` field on every catalog entry.
