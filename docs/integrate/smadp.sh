#!/usr/bin/env bash
# Integrate ONEXUS-Agents into SMADP.
#
# Installs the typed client into SMADP's uv venv, then (with your
# explicit ok) runs a sync from the catalog into
# catalog/profiles/_unverified/.
#
# Reads:
#   SMADP_REPO              (default: ~/Downloads/Integration/SMADP)
#   ONEXUS_AGENTS_REPO      (default: ~/Downloads/Integration/ONEXUS-Agents)
#
# Idempotent. Pure additive operations only.

set -euo pipefail

SMADP_REPO="${SMADP_REPO:-$HOME/Downloads/Integration/SMADP}"
ONEXUS_AGENTS_REPO="${ONEXUS_AGENTS_REPO:-$HOME/Downloads/Integration/ONEXUS-Agents}"

GRAY="\033[90m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

say()  { echo -e "${CYAN}▸${RESET} $*"; }
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
err()  { echo -e "${RED}✗${RESET} $*" >&2; }
ask()  { read -r -p "$(echo -e "${YELLOW}?${RESET} $* ${GRAY}[y/N]${RESET} ")" REPLY; [[ $REPLY =~ ^[Yy]$ ]]; }

# ── preflight ───────────────────────────────────────────────────────────
say "Preflight"
[[ -d "$SMADP_REPO" ]] || { err "SMADP not at $SMADP_REPO (override with SMADP_REPO=...)"; exit 1; }
[[ -d "$SMADP_REPO/.venv" ]] || { err "SMADP venv missing — cd $SMADP_REPO && uv sync first"; exit 1; }
[[ -f "$SMADP_REPO/uv.lock" ]] || warn "no uv.lock — SMADP may use a different package manager"
ok "SMADP at $SMADP_REPO with .venv"

# Ensure catalog is cloned somewhere we can use it (local mode is much
# faster than fetching 8k JSONs over HTTP).
if [[ ! -d "$ONEXUS_AGENTS_REPO/catalog" ]]; then
  warn "ONEXUS-Agents not at $ONEXUS_AGENTS_REPO"
  if ask "Clone it now?"; then
    git clone https://github.com/AllStreets/ONEXUS-Agents.git "$ONEXUS_AGENTS_REPO"
    ok "cloned"
  else
    err "need a local catalog clone — set ONEXUS_AGENTS_REPO=... and rerun"
    exit 1
  fi
else
  ok "ONEXUS-Agents at $ONEXUS_AGENTS_REPO"
fi

# Refresh catalog if it's stale.
if [[ -d "$ONEXUS_AGENTS_REPO/.git" ]]; then
  pushd "$ONEXUS_AGENTS_REPO" >/dev/null
  LAST_FETCH=$(git log -1 --format=%ct origin/main 2>/dev/null || echo 0)
  if (( $(date +%s) - LAST_FETCH > 86400 )); then
    if ask "Catalog's local copy looks older than a day — pull latest?"; then
      git pull --rebase
    fi
  fi
  popd >/dev/null
fi

# ── install ─────────────────────────────────────────────────────────────
cd "$SMADP_REPO"
say "Activating SMADP venv"
# shellcheck disable=SC1091
source .venv/bin/activate

say "Installing onexus-agents-pipeline[client] into SMADP venv"
if uv pip install "onexus-agents-pipeline[client] @ git+https://github.com/AllStreets/ONEXUS-Agents.git" 2>&1 | tail -3; then
  ok "client installed"
else
  err "install failed — see output above"
  exit 1
fi

# Sanity check the entry point.
if ! command -v onexus-agents-smadp-sync >/dev/null; then
  err "onexus-agents-smadp-sync not on PATH — venv issue?"
  exit 1
fi
ok "onexus-agents-smadp-sync available"

# ── sync ────────────────────────────────────────────────────────────────
OUT="$SMADP_REPO/catalog/profiles/_unverified"
mkdir -p "$OUT"
BEFORE_COUNT=$(find "$OUT" -maxdepth 1 -name "*.json" | wc -l | tr -d ' ')
say "Current _unverified seed count: $BEFORE_COUNT"

say "Dry run first (writes nothing)"
onexus-agents-smadp-sync \
  --catalog "$ONEXUS_AGENTS_REPO" \
  --out "$OUT" \
  --runnable-only \
  --skip-existing \
  --dry-run

if ! ask "Proceed for real? Writes new JSONs only — won't touch the $BEFORE_COUNT existing files."; then
  warn "Stopped after dry-run. No changes made."
  exit 0
fi

onexus-agents-smadp-sync \
  --catalog "$ONEXUS_AGENTS_REPO" \
  --out "$OUT" \
  --runnable-only \
  --skip-existing

AFTER_COUNT=$(find "$OUT" -maxdepth 1 -name "*.json" | wc -l | tr -d ' ')
ADDED=$((AFTER_COUNT - BEFORE_COUNT))
ok "wrote $ADDED new seeds · _unverified total now $AFTER_COUNT"

say "Verify:"
echo -e "    ${GRAY}cd $SMADP_REPO${RESET}"
echo -e "    ${GRAY}git status catalog/profiles/_unverified/${RESET}"
echo -e "    ${GRAY}cat catalog/profiles/_unverified/\$(ls catalog/profiles/_unverified/ | tail -1)${RESET}"
echo ""
say "If the schema looks right, commit:"
echo -e "    ${GRAY}git add catalog/profiles/_unverified/${RESET}"
echo -e "    ${GRAY}git commit -m \"chore(catalog): seed _unverified from ONEXUS-Agents ($ADDED new runnable agents)\"${RESET}"
