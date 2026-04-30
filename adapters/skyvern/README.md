# skyvern — MCP adapter

Bridges [Skyvern](https://github.com/Skyvern-AI/skyvern) into ONEXUS via MCP.

## Install

```sh
pip install skyvern
pip install "onexus-agents-pipeline[adapters]"
```

For self-hosted backend, follow the [Skyvern self-hosted guide](https://docs.skyvern.com/running-skyvern/quickstart) before pointing `SKYVERN_BASE_URL` at it.

## Invoke from ONEXUS

```sh
onexus call skyvern --task "log in to portal.example.com using stored creds and download the Q1 invoice PDF"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `run_task`.
3. Stream every step (navigate, click, type) through the MONITOR gate before execution.

## Defaults

- Tier: `MONITOR` — every browser action is reviewed before execution.
- Trust floor: `0.70` — agent can authenticate and submit forms; not for unattended runs.
- Backend: Skyvern Cloud by default; override with `SKYVERN_BASE_URL` for self-hosted.
- Bench: WebArena 31.4 (2026-02-12).
- License: AGPL-3.0 — review before bundling into closed deployments.
