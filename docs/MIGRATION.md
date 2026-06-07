# Migrating ONEXUS-Agents to a new Mac

Everything that matters for this project lives in one of three places:

1. **GitHub** — code, catalog data, CI secrets, workflow runs.
2. **Vercel** — site deployment, env vars, project settings.
3. **Your machine** — Claude session/memory state, local clones, browser auth.

Almost all of #1 and #2 transfers for free (they're remote). This doc covers
the bits that touch your laptop.

## Three commands on the new Mac

Open Terminal on the new Mac and run:

```bash
# 1. Install Xcode CLT (provides git). macOS will prompt; click Install.
xcode-select --install || true

# 2. Clone the repo
git clone https://github.com/AllStreets/ONEXUS-Agents.git ~/Downloads/ONEXUS-Agents
cd ~/Downloads/ONEXUS-Agents

# 3. Bootstrap (installs Homebrew, python@3.12, node, pnpm, gh,
#    plus pipeline + site deps, then runs a validator smoke check).
./docs/setup-new-mac.sh
```

That gets you a working pipeline + site. The script is idempotent — re-run it
any time without harm.

## Interactive logins (cannot be automated)

After the script finishes:

```bash
gh auth login          # GitHub CLI — pick HTTPS + browser
claude                 # Claude Code — first run prompts login
vercel login           # only if you deploy the site from this Mac
```

## Carry over Claude memory + session history (optional)

Claude Code keeps per-project memory and conversation logs at
`~/.claude/projects/-Users-connorevans-Downloads-ONEXUS-Agents/`. If you want
your old conversations and saved preferences to land on the new Mac, run this
on the **old Mac**:

```bash
rsync -av --progress \
  ~/.claude/projects/-Users-connorevans-Downloads-ONEXUS-Agents/ \
  <new-mac-hostname-or-ip>:~/.claude/projects/-Users-connorevans-Downloads-ONEXUS-Agents/
```

Find the new Mac's hostname under System Settings -> General -> Sharing
(it shows as `something.local`).

Alternatively, copy the directory to a USB stick / iCloud Drive and move it
manually. Path must match exactly — the directory name encodes the project
path.

## Session highlights — what Claude already knows about this project

If you start a fresh session on the new Mac WITHOUT migrating memory, paste
this into the first message so Claude has context:

**Project shape:**
- Daily nightly crawl (`pipeline/nightly.py`, runs 13:00 UTC via GitHub
  Actions in `.github/workflows/nightly.yml`) crawls GitHub + Hugging Face,
  ranks per-category by a composite score, keeps top 250.
- Catalog data: `catalog/<category>/<slug>.json`, validated by
  `validator/validate_submission.py` (schema in `pipeline/schema.py`).
- Site: Astro 4 + Tailwind v4 in `site/`, deployed to Vercel.
- Aesthetic: dark mono, cyan accent, JetBrains Mono. No emoji anywhere
  (icons via Lucide preferred).

**Hard-won invariants — don't violate these:**
- The catalog must only shrink via ranking-based truncation, never via missing
  API responses. `_discover` and `_refresh_seeds` must fold prior on-disk
  entries back into `by_cat` before `_write_and_truncate` wipes directories,
  or transient 403s will delete entries. See PR #23.
- Per-entry features (`runnable`, `adapter_ref`, `benchmarks`) must be sticky
  across rebuilds. `merge_overrides` and `merge_benchmarks` handle this. See
  PRs #20, #28.
- `gh pr merge --auto` fails with "unstable status" if checks haven't
  registered. The workflow polls `mergeStateStatus` until it leaves UNKNOWN
  before calling `--auto`. See PR #25.
- `--delete-branch` runs as a separate `continue-on-error` step — 403 rate
  limits on cleanup must not fail the job. See PR #28.
- Runnable auto-detection: GitHub topic `mcp-server` / `model-context-protocol`
  flips `runnable=true` + `adapter_ref="mcp/stdio"`. Author-declared signal
  only — broader heuristics risk false positives. See `pipeline/build.py`
  `detect_mcp_runnability()`.

**Current scale (as of last migration update):**
- ~2,000+ agents across 40 categories
- ~65 runnable
- Catalog grows daily via the bot's auto-merge PR flow

## What does NOT need migrating

- `.venv/`, `node_modules/`, `.ruff_cache/`, `.pytest_cache/` — gitignored,
  rebuilt by `setup-new-mac.sh`.
- `.env*` files — none exist; all secrets live in GitHub Actions secrets and
  Vercel env vars.
- `uv.lock`, `dist/`, `.astro/`, `.vercel/` — gitignored / regenerable.
- Local screenshots (`*.png` in repo root) — gitignored dev artifacts.

## Sanity check

After everything is set up:

```bash
cd ~/Downloads/ONEXUS-Agents
source .venv/bin/activate
onexus-agents-validate              # full catalog passes schema
cd site && pnpm dev                 # site comes up at http://localhost:4321
gh run list --workflow nightly -L 3 # see the bot's recent crawls
```

If all three work, you're done.
