# SWE-agent — MCP adapter

Bridges [SWE-agent](https://github.com/princeton-nlp/SWE-agent) into ONEXUS via MCP.

## Install

```sh
pip install sweagent
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call swe-agent \
  --task "fix the off-by-one in src/parser.py reported in issue #481" \
  --env REPO_PATH=/abs/path/to/repo
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `solve_issue`.
3. Stream the ACI (Agent-Computer Interface) trace back through the MONITOR gate.

## Defaults

- Tier: `MONITOR` — every shell command is reviewed in real time.
- Trust floor: `0.65` — agent edits source in-place; not for unattended runs.
- Model: `claude-sonnet-4-6` by default; override with `MODEL_NAME` (and the matching API key).
- Bench: SWE-bench Verified 33.6 (2026-03-15).
