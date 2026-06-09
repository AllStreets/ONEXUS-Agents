#!/usr/bin/env bash
# Integrate ONEXUS-Agents into NEXUS.
#
# Installs the typed client + MCP-server extra into NEXUS's venv. The
# remaining step — editing nexus/mcp/tools.py to add the three new tool
# definitions + handlers — is hand-printed at the end so you can paste
# it into the live file (which you may be actively editing).
#
# Reads:
#   NEXUS_REPO              (default: ~/Downloads/Integration/NEXUS)

set -euo pipefail

NEXUS_REPO="${NEXUS_REPO:-$HOME/Downloads/Integration/NEXUS}"

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
[[ -d "$NEXUS_REPO" ]] || { err "NEXUS not at $NEXUS_REPO (override with NEXUS_REPO=...)"; exit 1; }
[[ -d "$NEXUS_REPO/.venv" ]] || { err "NEXUS venv missing — cd $NEXUS_REPO && python3 -m venv .venv && source .venv/bin/activate && pip install -e ."; exit 1; }
[[ -f "$NEXUS_REPO/nexus/mcp/tools.py" ]] || { err "nexus/mcp/tools.py missing — NEXUS layout may have changed"; exit 1; }
ok "NEXUS at $NEXUS_REPO with venv + nexus/mcp/tools.py"

# ── install ─────────────────────────────────────────────────────────────
cd "$NEXUS_REPO"
say "Activating NEXUS venv"
# shellcheck disable=SC1091
source .venv/bin/activate

say "Installing onexus-agents-pipeline[client] into NEXUS venv"
if pip install "onexus-agents-pipeline[client] @ git+https://github.com/AllStreets/ONEXUS-Agents.git" 2>&1 | tail -3; then
  ok "client installed"
else
  err "install failed — see output above"
  exit 1
fi

# Sanity: does the import work?
if python -c "from pipeline.client import OnexusAgentsClient; OnexusAgentsClient.from_url()" 2>/dev/null; then
  ok "client imports cleanly"
else
  err "client install succeeded but import fails — check pip output above"
  exit 1
fi

# ── patch instructions ──────────────────────────────────────────────────
PATCH_FILE="$(dirname "$0")/nexus-tools-patch.py"
echo ""
say "Final step: hand-edit ${GRAY}nexus/mcp/tools.py${RESET} to add the three new tools."
say "The exact code to paste is in:"
echo "    $PATCH_FILE"
echo ""
say "What to do, step by step:"
cat <<'EOF'

  1. Open nexus/mcp/tools.py in your editor.

  2. Near the top with the other imports, add:

         from pipeline.client import OnexusAgentsClient

  3. Below the existing TOOL_DEFINITIONS list, add the 3 dicts shown in
     nexus-tools-patch.py (search for "nexus_agents_browse").

  4. Inside the ToolHandlers class (or wherever existing handlers live),
     add the 3 methods nexus_agents_browse / search / info from the
     same patch file.

  5. Save. Then:

         source .venv/bin/activate
         python -m nexus.mcp.server   # smoke test the server starts

  6. Connect from Claude Desktop / Cursor / your MCP client and call
     the new tools. Expected: nexus_agents_search("langchain") returns
     a list of langchain-based agents.

EOF

if ask "Show the patch contents now?"; then
  cat "$PATCH_FILE"
fi

echo ""
ok "Install complete. Code edit is yours to apply."
