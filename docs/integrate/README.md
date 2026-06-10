# Integrate ONEXUS-Agents into NEXUS + SMADP

Two ready-to-run helpers. **Run one. Test. Verify. Then run the other.**

| Script | Target repo | What it does | Reversible? |
|---|---|---|---|
| [`smadp.sh`](smadp.sh) | `~/Downloads/Integration/SMADP` | Installs the typed client into SMADP's uv venv. Optionally syncs every runnable catalog agent into `catalog/profiles/_unverified/`. | Yes — `git restore catalog/profiles/_unverified/` |
| [`nexus.sh`](nexus.sh) | `~/Downloads/Integration/NEXUS` | Installs the typed client + MCP-server extra into NEXUS's venv. Prints the exact patch for `nexus/mcp/tools.py`. | Yes — uninstall the package, revert the tools.py edit |

Each script is **idempotent** — safe to re-run as the upstream projects evolve.
Each script **prints what it's about to do BEFORE doing it** and prompts for confirmation at any irreversible step.

## Recommended order

1. **SMADP first** — purely additive (writes new files into a directory). No code edit needed. Faster to verify.
2. **NEXUS second** — needs a code edit in `nexus/mcp/tools.py`. The script prints the exact lines to paste and won't modify anything outside the venv install.

## After running each, verify with:

```bash
# SMADP
cd ~/Downloads/Integration/SMADP
ls catalog/profiles/_unverified/ | wc -l       # should have grown
git diff catalog/profiles/_unverified/         # eyeball one or two

# NEXUS
cd ~/Downloads/Integration/NEXUS
source .venv/bin/activate
python -c "from pipeline.client import OnexusAgentsClient; c = OnexusAgentsClient.from_url(); print(len(c.runnable_only()))"
# should print a number > 700
```

## If something goes wrong

- The scripts log everything they do; nothing is silent
- `pip uninstall onexus-agents-pipeline` reverses the install in either venv
- For SMADP: `git restore catalog/profiles/_unverified/` reverses any sync
- For NEXUS: revert the `tools.py` edit, then `git checkout -- nexus/mcp/tools.py`

## Inputs you can override

Both scripts pick reasonable defaults. Override via env vars:

```bash
ONEXUS_AGENTS_REPO=/path/to/ONEXUS-Agents    # default: ~/Downloads/Integration/ONEXUS-Agents
NEXUS_REPO=/path/to/NEXUS                    # default: ~/Downloads/Integration/NEXUS
SMADP_REPO=/path/to/SMADP                    # default: ~/Downloads/Integration/SMADP
```
