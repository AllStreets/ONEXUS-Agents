# browser-use — MCP adapter

Bridges [browser-use](https://github.com/browser-use/browser-use) into ONEXUS via MCP.

## Install

```sh
pip install browser-use
playwright install chromium
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call browser-use --task "find the highest-rated coffee shop within a mile of Times Square on Google Maps and copy its address"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `run_task`.
3. Stream every step through the MONITOR gate.

## Defaults

- Tier: `MONITOR` — every browser action is reviewed before execution.
- Trust floor: `0.65` — agent can authenticate and submit forms; not for unattended runs.
- Model: `claude-sonnet-4-6` by default; override with `MODEL_NAME` (and the matching API key).
- Bench: WebArena 39.2 (2026-03-04).
