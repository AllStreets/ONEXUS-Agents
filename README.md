# ONEXUS-Agents

> **The largest continuously-updated public catalog of the world's most powerful open-source AI agents.**
> Over **7,000 agents** indexed across 40 task categories. Hundreds runnable today via MCP.
> Discovered nightly. Ranked transparently. Bridged into ONEXUS on demand.

`license: Apache-2.0`  ·  `python: 3.12`  ·  `node: 24.x`  ·  `update cadence: 13:00 UTC daily + 17:00 UTC Sundays`

---

## What this is

ONEXUS-Agents is the public, open-source arm of [ONEXUS](https://github.com/AllStreets/ONEXUS) — the agentic OS kernel.

ONEXUS itself is a closed-loop runtime: Cortex routes intent, Engram remembers, Pulse schedules, Chronicle audits, Aegis enforces. It is the brain.

**ONEXUS-Agents is the body's reach.** It is the catalog the kernel looks at when it needs an external skill: a coding agent, a browser agent, a legal-research agent, a video-generation pipeline. We crawl GitHub and Hugging Face every night, score every candidate against a transparent composite of popularity, recency, runnability, quality signals, and (where one exists) a real benchmark, and publish the top 500 agents per category as static JSON.

The catalog is the product. The dashboard is the showcase. The MCP bridge is the on-ramp.

## How it works

Two scheduled jobs keep the catalog fresh:

```
nightly · 13:00 UTC daily                weekly · 17:00 UTC Sundays
        │                                        │
        ▼                                        ▼
  refresh seeds                            re-scan every entry for
        │                                  README-aware MCP signals
        ▼                                        │
  auto-discover from GitHub + HF                 ▼
  (315 hand-curated queries +              enrich staleset 500 with
   384 auto-broadened keyword queries)     Tier 2 metrics (contributors,
        │                                  releases, commit cadence, CI)
        ▼                                        │
  classify (keyword first, free;                 ▼
  OpenAI gpt-5.4-mini only when           open auto-merge PR
  truly ambiguous)
        │
        ▼
  score (composite, multi-signal)
        │
        ▼
  per-category cap (500 featured + tail tier)
        │
        ▼
  daily report → reports/YYYY-MM-DD.md
        │
        ▼
  open auto-merge PR → Vercel rebuilds dashboard
```

Every agent in the catalog is a single JSON file under `catalog/<category>/<agent-slug>.json`. No database. The git history *is* the audit log.

A subset of catalogued agents are marked `runnable: true` and have an `adapter_ref` — that's the MCP wrapper ONEXUS uses to actually invoke them. Browse them at **[/runnable](https://agents.onexus.dev/runnable)**. Discovery is broad; runnable is curated and grows weekly as the Sunday rescan finds new MCP-server-shaped repos.

## The 40 categories

Each category gets a top-500 featured leaderboard. Anything ranked past 500 that still passes a quality threshold lands in `catalog/<cat>/_tail/` for long-tail discoverability. Eight categories anchor on a real, peer-recognised benchmark that contributes 30% of the composite score; the others score on popularity, recency, age, runnability, quality signals, and framework detection.

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
    "forks": 3100,
    "watchers": 280,
    "open_issues": 412,
    "archived": false,
    "is_fork": false,
    "is_template": false,
    "downloads_30d": null,
    "last_commit_at": "2026-04-22T14:01:00Z",
    "first_commit_at": "2023-05-09T00:00:00Z",
    "contributors_count": 87,
    "releases_total": 142,
    "latest_release_at": "2026-04-20T00:00:00Z",
    "commits_90d": 312,
    "has_ci": true,
    "readme_length": 18432,
    "frameworks": ["mcp"]
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
  "last_refreshed_at": "2026-06-07T00:00:00Z",
  "consecutive_refresh_failures": 0
}
```

## Submitting an agent

Two paths. Most submitters want the form.

**Fastest — open an issue:** Use the **[Submit an agent](https://github.com/AllStreets/ONEXUS-Agents/issues/new?template=agent-submission.yml)** issue template. Fill in source, repo, category, license. A workflow fetches the real GitHub/HF metadata, validates, and opens an auto-merging PR. No fork, no clone, no JSON.

**Hand-authored PR:** For larger or custom entries (multi-source, hand-written adapter, benchmark scores):

1. Fork the repo.
2. Add `catalog/<category>/<your-agent>.json` matching the schema above.
3. Open a PR using the **Agent submission** template.
4. CI runs `onexus-agents-validate`. If it passes, an admin reviews and merges.

You do *not* need to compute `composite_score`, `rank_in_category`, or any Tier 2 metrics — the daily and weekly jobs recompute those for everything in the catalog. Hand-authored entries become first-class members of the ranking pool the next day after merge.

## ONEXUS integration

ONEXUS reads this catalog directly. Point `NEXUS_AGENTS_CATALOG` at a local clone:

```bash
git clone https://github.com/AllStreets/ONEXUS-Agents.git
export NEXUS_AGENTS_CATALOG=/path/to/ONEXUS-Agents
onexus run
```

Three MCP tools expose the catalog inside ONEXUS:

| Tool | What it does |
|------|-------------|
| `nexus_agents_browse` | List agents by category, filter to runnable-only |
| `nexus_agents_search` | Keyword search across names, tags, categories |
| `nexus_agents_info` | Full metadata + MCP adapter descriptor for a specific agent |

When a user asks ONEXUS for help with a task, Cortex looks at the relevant category, picks among `runnable: true` candidates by composite score and trust history, and dispatches via the agent's MCP adapter.

The adapter contract is intentionally thin:

```
adapters/<agent>/mcp.json    # MCP server descriptor -- command, env, capabilities
adapters/<agent>/README.md   # one-line install, one-line invocation
```

MCP-first, with an escape hatch for agents that don't speak MCP yet (a small Python adapter shim).

## Methodology

The composite score is fully public. With a benchmark anchor:

```
0.30 * benchmark
+ 0.15 * stars (log-normalized)
+ 0.07 * forks (log-normalized)
+ 0.10 * downloads (log-normalized, HF only)
+ 0.13 * recency (last commit, 90-day half-life)
+ 0.05 * age (project maturity, 24-month cap)
+ 0.05 * runnable (binary)
+ 0.15 * quality (composite — see below)
```

Without a benchmark anchor:

```
0.22 * stars
+ 0.10 * forks
+ 0.15 * downloads
+ 0.20 * recency
+ 0.05 * age
+ 0.05 * runnable
+ 0.23 * quality
```

Then **multiplicative penalties**: `archived` × 0.5, `is_template` × 0.8. An archived 5k-star repo will always rank below a live 1k-star competitor on otherwise-equal signals.

The `quality` sub-score (0–1) combines: archived flag, fork/template status, semantic identity (HF `library_name`/`pipeline_tag` presence), open-issue activity, watcher count, and **framework detection** (langchain, llamaindex, crewai, autogen, smolagents, dspy, openai-agents-sdk, anthropic-sdk, mcp, transformers, gradio — detected from tags, tagline, and README during the weekly rescan).

Entries ranked past the per-category featured cap (500) that still pass the quality threshold (≥ 0.20 composite) land in `catalog/<cat>/_tail/` — searchable but not on the main category page. Everything else is logged in `catalog/_dropped/<date>.json` so the displacement is fully auditable.

Catalog hygiene: entries that fail to refresh for 28 consecutive nightlies (≈4 weeks of 404, archived, or rate-limited responses) are dropped automatically. A transient outage never removes anything; sustained absence does.

## Layout

```
catalog/         per-category JSON files (the catalog itself)
  <cat>/         featured entries (top 500 by composite)
  <cat>/_tail/   long-tail entries (passing quality threshold)
  _dropped/      audit log of removed slugs per date
seeds/           hand-curated YAML seeds per category
adapters/        MCP wrappers for runnable agents
pipeline/        ingestion + scoring + reporting (Python 3.12)
  crawlers/      GitHub + Hugging Face fetchers
  benchmarks/    benchmark scrapers
  budget.py      per-run API budget cap (free-tier safe)
  ranking.py     composite score + quality sub-score
  classifier.py  keyword + OpenAI gpt-5.4-mini category classifier
  frameworks.py  Tier 3 framework detection
  report.py      daily quality summary
validator/       schema + PR validation
reports/         daily quality summaries (one MD per day)
site/            Astro 4 + Tailwind v4 dashboard
.github/         workflows + issue/PR templates
docs/            design specs and methodology
```

## Local development

```sh
# Pipeline
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
onexus-agents-validate catalog/coding/aider.json
onexus-agents-nightly --dry-run
onexus-agents-weekly --dry-run

# Site
cd site && pnpm install && pnpm dev
```

## Pipeline ops

The system runs unattended end-to-end:

- **Nightly 13:00 UTC** — discover + classify + score + report + auto-merge PR
- **Weekly 17:00 UTC Sundays** — README-aware runnable rescan + Tier 2 metric enrichment + auto-merge PR
- **Submissions** — issue-form → PR with API-reconciled metadata → auto-merge

Free-tier safe: a hard per-run API budget cap (12,000 GH calls default, raised to 30,000 if a `GH_PAT` secret is set; 5,000 HF; bounded OpenAI call budget). If anything fails — workflow timeout, conflict, OpenAI billing, budget exhaustion — a `bot-failure` GitHub issue auto-opens with the run URL, conclusion, and likely-culprit checklist.

## License

Apache-2.0. Copyright 2026 AllStreets.

Agent metadata and rankings are publicly redistributable. Each catalogued agent retains its own upstream license — see the `license` field on every catalog entry. The catalog as a whole is free for commercial and non-commercial use under the Apache 2.0 terms, including the patent grant.
