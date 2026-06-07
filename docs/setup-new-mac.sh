#!/usr/bin/env bash
# Idempotent bootstrap for a fresh macOS dev environment.
# Safe to re-run — every step checks before installing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

log() { printf "\n[setup] %s\n" "$*"; }

# 1. Homebrew
if ! command -v brew >/dev/null 2>&1; then
  log "installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -d /opt/homebrew/bin ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
else
  log "Homebrew present: $(brew --version | head -1)"
fi

# 2. CLI tooling
NEEDED_BREW=(git gh python@3.12 node pnpm)
MISSING=()
for pkg in "${NEEDED_BREW[@]}"; do
  if ! brew list --formula "$pkg" >/dev/null 2>&1; then
    MISSING+=("$pkg")
  fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  log "installing: ${MISSING[*]}"
  brew install "${MISSING[@]}"
else
  log "all brew packages present"
fi

# 3. Python venv + pipeline deps
if [ ! -d .venv ]; then
  log "creating .venv with python 3.12"
  "$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
fi
log "installing pipeline (editable + dev extras)"
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -e ".[dev]" >/dev/null

# 4. Site deps
if [ -d site ]; then
  log "installing site deps via pnpm"
  (cd site && pnpm install --frozen-lockfile)
fi

# 5. Smoke check
log "smoke check: validator"
./.venv/bin/onexus-agents-validate >/dev/null && echo "validator OK"

log "done."
cat <<'EOF'

Next steps that need YOUR interactive input (cannot be automated):

  1. gh auth login         # GitHub CLI auth (pick HTTPS + browser)
  2. claude                # log into Claude Code on first run
  3. (optional) vercel login   # if you deploy the site from this Mac

If you want to carry over Claude memory/sessions from your old Mac, run
this on the OLD Mac:

  rsync -av ~/.claude/projects/-Users-connorevans-Downloads-ONEXUS-Agents/ \
    new-mac.local:~/.claude/projects/-Users-connorevans-Downloads-ONEXUS-Agents/

EOF
