# ONEXUS-Agents — Design Spec

**Date:** 2026-04-29
**Status:** Approved by user, ready for implementation
**Owner:** AllStreets

---

## 1. Purpose

ONEXUS-Agents is the public-facing open-source arm of the ONEXUS project. It exists to be **the largest, continuously-updated catalog of the world's most powerful open-source agents**, organized into ~40 narrowly-scoped task categories, ranked by a transparent benchmark-anchored composite score, refreshed every night, and bridged into the ONEXUS kernel via the Model Context Protocol (MCP).

Two tiers:

- **Discovery tier** — every qualifying agent is cataloged and browsable on the dashboard, with full attribution, stats, and source links.
- **Runnable tier** — the subset of agents reachable via MCP (either upstream-native or wrapped by an adapter shipped here) gets a "Use in ONEXUS" treatment and is invocable from the kernel.

ONEXUS-Agents is a separate project from ONEXUS itself. The kernel (https://github.com/AllStreets/ONEXUS) does not depend on this repo. This repo consumes a small ONEXUS contract surface (MCP) but otherwise operates standalone.

---

## 2. System shape (one paragraph)

The catalog is **JSON files committed to this repo**, one per agent, organized as `catalog/<category>/<agent>.json`. A nightly GitHub Actions cron at 00:00 UTC runs the ingestion pipeline (Python), which crawls GitHub Search and the Hugging Face Hub, refreshes seeds, classifies new candidates into categories, scores everything by a composite, truncates to the top 100 per category, and commits the diff back to `main`. A Vercel deploy fires on every push and rebuilds the static Astro dashboard, which reads the JSON catalog at build time. Submissions are pull requests against `catalog/`; CI runs a schema validator on each PR; the admin (the project owner) reviews and merges.

---

## 3. Repository layout

```
ONEXUS-Agents/
├── LICENSE
├── README.md
├── pyproject.toml                          # Python package for pipeline + validator
├── package.json                            # Astro workspace at site/
├── .gitignore
├── .python-version
├── docs/
│   └── superpowers/specs/                  # design specs (this file lives here)
├── catalog/                                # SOURCE OF TRUTH — JSON catalog
│   ├── _categories.json                    # 40 category defs
│   └── <category>/<agent>.json             # ~4,000 agent files at full population
├── seeds/                                  # admin-curated seed lists
│   └── <category>.yaml
├── adapters/                               # MCP wrappers for non-MCP-native agents
│   ├── README.md                           # how to write an adapter
│   ├── aider.py
│   └── open_interpreter.py
├── pipeline/                               # ingestion + ranking (Python)
│   ├── __init__.py
│   ├── nightly.py                          # entry point for cron
│   ├── crawlers/
│   │   ├── github.py
│   │   └── huggingface.py
│   ├── classifier.py                       # category placement
│   ├── ranking.py                          # composite scoring
│   ├── benchmarks/
│   │   ├── __init__.py
│   │   ├── swe_bench.py
│   │   ├── gaia.py
│   │   └── stub.py                         # for categories without leaderboards
│   └── schema.py                           # pydantic model for catalog JSON
├── validator/
│   └── validate_submission.py              # used by CI on submission PRs
├── site/                                   # Astro dashboard
│   ├── astro.config.mjs
│   ├── tailwind.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── public/
│   └── src/
│       ├── pages/
│       │   ├── index.astro
│       │   ├── catalog/
│       │   │   ├── index.astro
│       │   │   └── [category]/
│       │   │       ├── index.astro
│       │   │       └── [agent].astro
│       │   ├── submit.astro
│       │   ├── methodology.astro
│       │   └── about.astro
│       ├── components/
│       ├── layouts/
│       ├── lib/                            # catalog loader, formatters
│       └── styles/
└── .github/
    ├── workflows/
    │   ├── nightly.yml                     # cron 00:00 UTC
    │   ├── validate-submission.yml         # on PRs touching catalog/
    │   └── deploy.yml                      # Vercel hook (or use Vercel's GH integration directly)
    └── PULL_REQUEST_TEMPLATE/
        └── new-agent.md
```

---

## 4. Catalog schema

Per-agent JSON file at `catalog/<category-slug>/<agent-slug>.json`. Validated by `pipeline/schema.py` (pydantic).

```json
{
  "slug": "cline",
  "name": "Cline",
  "tagline": "Autonomous coding agent that plans, edits files, runs commands, and uses the browser — fully in your IDE.",
  "category": "coding",
  "tags": ["typescript", "vscode", "mcp", "browser"],

  "author": { "name": "cline", "url": "https://github.com/cline" },
  "source": {
    "type": "github",
    "url": "https://github.com/cline/cline",
    "homepage": "https://cline.bot"
  },
  "license": "Apache-2.0",

  "metrics": {
    "stars": 38400,
    "downloads_monthly": 890000,
    "last_commit_at": "2026-04-27T14:22:00Z",
    "first_commit_at": "2024-07-01T00:00:00Z",
    "age_days": 668
  },

  "benchmarks": [
    {
      "name": "SWE-bench Verified",
      "score": 54.2,
      "unit": "%",
      "leaderboard_url": "https://www.swebench.com/"
    }
  ],

  "runnable": {
    "mode": "native_mcp",
    "mcp_config": {
      "command": "npx",
      "args": ["-y", "cline-mcp-server"],
      "env": {}
    },
    "wrapper_path": null
  },

  "composite_score": 96.4,
  "rank_in_category": 1,

  "discovered_via": "seed",
  "first_seen_at": "2026-01-15T00:00:00Z",
  "last_refreshed_at": "2026-04-29T00:00:00Z"
}
```

**Field notes:**
- `slug` — lowercase, alphanumeric + dashes, must be unique within `(category, slug)`.
- `category` — must match a `slug` in `_categories.json`.
- `tags` — free-form, lowercased.
- `metrics` — populated by crawlers.
- `benchmarks` — array; empty for categories without leaderboards.
- `runnable.mode` — `"native_mcp"`, `"wrapper"`, or `null`. `null` means discovery-tier only.
- `runnable.wrapper_path` — path relative to repo root (e.g. `"adapters/aider.py"`) when `mode == "wrapper"`.
- `composite_score` — float 0–100, computed by `pipeline/ranking.py`.
- `rank_in_category` — integer 1–100, computed nightly.
- `discovered_via` — `"seed"`, `"search"`, or `"submission"`.

---

## 5. Categories & taxonomy

Single source of truth: `catalog/_categories.json`. Approximately 40 categories. Schema:

```json
{
  "version": 1,
  "updated_at": "2026-04-29",
  "categories": [
    {
      "slug": "coding",
      "name": "Coding",
      "description": "General-purpose coding assistants — file editing, command execution, multi-file refactors, IDE integrations.",
      "benchmark_anchor": {
        "name": "SWE-bench Verified",
        "leaderboard_url": "https://www.swebench.com/",
        "weight_share": 0.30
      },
      "seed_keywords": [
        "coding agent", "swe-bench", "code assistant", "code editing agent",
        "ide agent", "autonomous coder"
      ],
      "github_search_queries": [
        "topic:coding-agent",
        "topic:swe-agent",
        "topic:ai-coding-assistant"
      ],
      "huggingface_filters": {
        "task_categories": ["text-generation"],
        "tags": ["agent", "coding"]
      }
    }
  ]
}
```

**Initial 40 categories** (slugs):

`coding`, `web-dev`, `data-engineering`, `data-science-ml`, `financial-modeling`, `legal-research`, `customer-support`, `content-writing`, `image-generation`, `video-generation`, `audio-speech`, `translation`, `search-rag`, `browser-automation`, `desktop-os-automation`, `document-processing`, `email-scheduling`, `devops-sre`, `security-pentesting`, `bioinformatics`, `scientific-research`, `education-tutoring`, `reasoning-math`, `multi-agent-orchestration`, `healthcare`, `travel-planning`, `sales-crm`, `marketing`, `social-media`, `e-commerce`, `real-estate`, `cooking`, `music`, `game-playing`, `robotics`, `knowledge-management`, `pdf-forms`, `spreadsheet-excel`, `sql-analytics`, `3d-cad`.

Free-form tags emerge from agent metadata; no fixed tag taxonomy.

---

## 6. Ingestion pipeline

`pipeline/nightly.py` is the GH Actions cron entry point. Steps:

### 6.1 Refresh seeds
For each `seeds/<category>.yaml` entry, fetch fresh metadata from the source (GitHub or HF Hub). Update the corresponding `catalog/<category>/<slug>.json` in place. Seeds are guaranteed to stay in the catalog regardless of ranking outcome.

### 6.2 Auto-discovery
For each category, run the search queries declared in `_categories.json`:
- **GitHub Search API** — issue queries for `github_search_queries`, fetch top N results.
- **Hugging Face Hub** — list Spaces/Models matching `huggingface_filters`.

Quality threshold for entry into the candidate pool:
- GitHub: `≥50 stars` AND `last commit within 365 days` AND README parses (non-empty, ≥200 chars).
- Hugging Face: `≥100 likes` OR `≥1000 downloads/mo`, AND model card non-empty.

Dedup against existing catalog by source URL.

### 6.3 Classify
For each new candidate, place into a category:
1. **Keyword match** — score the candidate's name + description + tags against each category's `seed_keywords`. If the top category beats the runner-up by ≥0.30, accept that placement.
2. **LLM fallback** — if keyword match is ambiguous, ask Claude Haiku ("Given these 40 categories with descriptions, which one best fits this agent? Reply with just the slug, or `none` if no fit."). Cache the answer keyed by source URL to avoid re-querying.
3. **Reject** — if neither method places the candidate, skip it (do not add to catalog).

### 6.4 Score
Compute `composite_score` (0–100) for every catalog entry. Weights:

For categories **with** a benchmark anchor:
- Stars (normalized log-scale within category): 18%
- Downloads/mo (normalized log-scale within category): 18%
- Recency (decay function, last commit within 7 days = 1.0, exponential decay): 14%
- Age maturity (age_days, normalized): 5%
- Runnable bonus (`+5` if `runnable.mode != null`): 5%
- Benchmark anchor (normalized within category): 30%
- Reserved/extensible: 10%

For categories **without** a benchmark anchor (the 30% benchmark slice redistributes proportionally to popularity signals):
- Stars: 28%
- Downloads/mo: 28%
- Recency: 22%
- Age maturity: 7%
- Runnable bonus: 5%
- Reserved/extensible: 10%

Composite score is published on every card and detail page. The methodology page documents these exact weights.

### 6.5 Truncate & rank
For each category, sort by `composite_score` descending and keep the top 100. Anything bumped out is **deleted** from `catalog/`. Assign `rank_in_category` 1–100. Update `last_refreshed_at` on every surviving entry.

### 6.6 Commit
Single commit:
```
chore(catalog): nightly refresh 2026-04-29 — +12 added, -8 dropped, 40 categories refreshed
```

GitHub Actions push triggers Vercel deploy. Static rebuild publishes the new catalog within minutes.

---

## 7. ONEXUS bridge (MCP-first)

ONEXUS speaks MCP via its existing `nexus/mcp/` module. ONEXUS-Agents only ever produces MCP-compatible runnables.

### 7.1 Two flavors of `runnable`

**Native MCP** — the upstream agent ships an MCP server. The catalog stores the MCP config block directly:
```json
"runnable": {
  "mode": "native_mcp",
  "mcp_config": { "command": "npx", "args": ["-y", "cline-mcp-server"], "env": {} }
}
```

**Wrapped** — the agent doesn't ship MCP, but is important enough that this repo ships a wrapper. Catalog points at the wrapper file:
```json
"runnable": {
  "mode": "wrapper",
  "wrapper_path": "adapters/aider.py"
}
```

### 7.2 Wrapper contract
Every file in `adapters/` exposes a single FastMCP server (`from mcp.server.fastmcp import FastMCP`). The wrapper installs and shells out to the upstream agent. `adapters/README.md` documents:
- The exact import path users add to ONEXUS's MCP config.
- The install command (`pip install <upstream-package>` or equivalent).
- The minimal tool surface the wrapper exposes.

### 7.3 Per-agent detail page integration
The agent detail page renders one of three states:
- `runnable.mode == "native_mcp"` — show "Add to ONEXUS" panel with the MCP config copy block + install command from the upstream README.
- `runnable.mode == "wrapper"` — show "Add to ONEXUS via adapter" panel with the wrapper path, install command, and a link to view the wrapper source.
- `runnable.mode == null` — show a "Discovery-only — no MCP interface yet" notice with a link to the upstream issue tracker, encouraging users to request MCP support.

The goal is for `mode == "wrapper"` to gradually disappear as upstream agents adopt MCP. Each wrapper is technical debt the wrapper deletion later resolves.

---

## 8. Dashboard (Astro + Tailwind)

### 8.1 Stack
- **Astro 4.x** for static-generated catalog pages (4,000+ pages at full population, all rendered at build time).
- **Tailwind CSS v4** for styling.
- **Custom components** matching the ONEXUS aesthetic (no opinionated component library).
- **Lucide icons** as inline SVG (no emoji anywhere).
- **Hydrated islands** only where interactivity is required: search bar, sortable column headers, tag filter row. Use Astro's island pattern with vanilla JS or a tiny Svelte island — no React unless we hit a specific need for it.
- **Fonts** — JetBrains Mono (numbers, identifiers, monospace UI), Inter (prose).
- **Palette** — bg `#07090c`, panel `#0a0d12`, border `#1f242c`, text-primary `#e6edf3`, text-secondary `#7a8693`, accent cyan `#00D4FF`, success `#3fb950`, warning `#d29922`.

### 8.2 Pages

| Path | Purpose |
|------|---------|
| `/` | Homepage — hero, "today by the numbers" stats strip (categories tracked, agents indexed, runnable count, last refresh time), featured 6 categories card grid, "latest catalog changes" mini-feed. |
| `/catalog` | Index of all 40 categories. Each row: name, one-line description, current top 5 with quick links. |
| `/catalog/[category]` | The Layout B leaderboard — top 100 of the category, sortable by composite/stars/downloads/recency/benchmark, tag-filter pills, runnable filter toggle. Each row → detail page. |
| `/catalog/[category]/[agent]` | Per-agent detail page — header (name + author + runnable badge + quick links to GH/HF/homepage), score breakdown panel (each weight component visualized), benchmark detail, README preview, "Use in ONEXUS" panel (state varies per `runnable.mode`), raw catalog JSON link, "discovered via X on YYYY-MM-DD" footer. |
| `/submit` | Submission instructions — what makes a good agent submission, the JSON fields required, and a prominent "Open New-Agent PR" button linking to the GitHub PR template URL. |
| `/methodology` | How ranking works — composite weights, benchmark sources, recency decay function, takedown policy, contact email. Canonical answer to "why does X rank here?" |
| `/about` | What ONEXUS is, link back to the kernel repo, credits, license, sponsorship contact. |

### 8.3 Visual DNA (Layout B)
Confirmed during brainstorming. Dense leaderboard rows: rank · glyph · name + tagline · stars · downloads/mo · last commit · score + benchmark · action icons. Sortable columns. Hover lift. Click row → detail page.

### 8.4 Catalog loader
`site/src/lib/catalog.ts` reads all `catalog/**/*.json` at build time using Astro's `import.meta.glob` (or a Node script in `astro.config.mjs`). Provides typed accessors: `getCategories()`, `getCategory(slug)`, `getAgentsByCategory(slug)`, `getAgent(category, slug)`. Sorting and filtering happen client-side for the small interactive surface (top 100 per category fits trivially in a JSON blob shipped with the page).

---

## 9. Submission flow

### 9.1 Submitter experience
1. Visit `/submit` on the dashboard.
2. Read the criteria.
3. Click "Open New-Agent PR" — opens a GitHub PR creation flow with the `new-agent.md` template prefilled.
4. Submitter creates `catalog/<category>/<their-agent-slug>.json`, fills in the schema, opens the PR.

### 9.2 PR template (`.github/PULL_REQUEST_TEMPLATE/new-agent.md`)
Walks the submitter through:
- Confirming the agent fits one of the existing 40 categories (link to `_categories.json`).
- Filling in the JSON template (all required fields, examples shown).
- Confirming the agent is OSS-licensed and they have authority to submit.
- Confirming they've read the methodology and ranking is data-driven (no requests to manually boost rank).

### 9.3 CI validation (`validator/validate_submission.py`)
Triggered by `validate-submission.yml` on any PR touching `catalog/`. Checks:
- Path matches `catalog/<existing-category>/<slug>.json`.
- Slug is unique within the category.
- JSON validates against the pydantic schema.
- `source.url` is reachable (HTTP HEAD, follows redirects).
- `license` is non-empty and matches a known SPDX identifier.
- `runnable` block (if non-null) is internally consistent (native_mcp → has mcp_config; wrapper → wrapper_path exists in repo).
- No `composite_score` / `rank_in_category` in the submission (these are computed nightly, not user-set).

### 9.4 Admin moderation
You review PRs in GitHub. Approval = merge. Merge fires Vercel deploy. The next nightly run scores the new entry; if it ranks below position 100 in its category, the next nightly will drop it (this is intentional — ranking is the equalizer).

---

## 10. CI workflows

### 10.1 `nightly.yml`
- Trigger: `schedule: cron: "0 0 * * *"` (00:00 UTC daily) and `workflow_dispatch` (manual run).
- Runs Python 3.12, installs `pyproject.toml`.
- Reads secrets: `GITHUB_TOKEN` (auto), `HF_TOKEN`, `ANTHROPIC_API_KEY` (for Haiku classifier fallback).
- Runs `python -m pipeline.nightly`.
- Commits diff with message `chore(catalog): nightly refresh YYYY-MM-DD — +N added, -M dropped`.
- Pushes to `main`.

### 10.2 `validate-submission.yml`
- Trigger: `pull_request` with `paths: [catalog/**]`.
- Runs Python 3.12, installs `pyproject.toml`.
- Runs `python -m validator.validate_submission $(git diff --name-only origin/main...HEAD -- 'catalog/*.json')`.
- Comments PR on validation failure with structured error list.

### 10.3 `deploy.yml` (optional)
- Vercel's GitHub integration handles auto-deploy on push to `main` natively. We may skip this workflow file entirely and configure Vercel directly.

---

## 11. Secrets & configuration

- `HF_TOKEN` — read-only Hugging Face Hub token (avoids strict anonymous rate limits).
- `ANTHROPIC_API_KEY` — for the Haiku classifier fallback in `pipeline/classifier.py`. Optional; pipeline degrades to keyword-only classification without it.
- `GITHUB_TOKEN` — provided automatically by GH Actions; used for Search API.

All three are configured as GitHub repository secrets. None are committed to the repo.

---

## 12. README & external presentation

The README mirrors the ONEXUS README's voice:
- Dark-theme mindset, JetBrains Mono badges in the header, no emoji.
- Confident technical prose, declarative section openers.
- ASCII-art-friendly section dividers where appropriate.
- Sections: hero, what ONEXUS-Agents is and why it exists, how it works (ingest → rank → publish → bridge), the 40 categories at a glance, the catalog file format, submitting an agent, ONEXUS integration, methodology link, license.

The README is the canonical landing page on GitHub; the dashboard is the canonical UX for discovery.

---

## 13. Out of scope (explicit)

- **No web form for submissions** — submitters use GitHub PRs. Discussed and accepted: submitters being slightly more technical is a fair tradeoff for zero serverless ops.
- **No user accounts, comments, or voting** — ranking is data-driven and the dashboard is read-only.
- **No private/paid agents** — open-source only. Commercial agents may be cataloged if the source is OSS-licensed; closed-source SaaS agents are out.
- **No agent runtime hosting** — we catalog and provide MCP config; users run the agents themselves via ONEXUS or directly.
- **No federation with other agent registries** — v1 ingests only from GitHub and Hugging Face. PyPI/npm/arXiv may be added later.
- **No LLM-based agent quality scoring** — too opaque to defend publicly. Composite is fully objective.
- **No deprecation of catalog entries via age alone** — only ranking determines presence. A 5-year-old agent that still ranks top-100 stays.
- **No badge or leaderboard widget for agent authors to embed** — could be added later as a v2 feature.

---

## 14. Implementation order (batches)

1. **Foundation** — repo skeleton, `pyproject.toml`, `package.json`, `_categories.json`, schema doc, README v1, `.gitignore`.
2. **Catalog seed data** — `seeds/<cat>.yaml` for the well-developed categories, 8–12 hand-authored sample catalog JSON files to anchor the schema.
3. **Dashboard** — Astro site with all pages from §8, locally runnable, reads from `catalog/`.
4. **Ingestion pipeline** — `pipeline/` with crawlers, classifier, ranking, benchmark fetchers, `nightly.py`. Locally runnable behind a `--dry-run` flag.
5. **Bridge layer** — `adapters/` with the contract README + reference wrappers for `aider` and `open-interpreter`.
6. **CI & validators** — GH Actions workflows, submission PR template, schema validator script.
7. **Polish** — final README pass, Vercel config, methodology page copy, takedown policy, dashboard styling final.

Each batch ends with a commit. Batch boundaries are verification points.
