# openhands — MCP adapter

Bridges [OpenHands](https://openhands.dev) (formerly OpenDevin) into ONEXUS via MCP.

## Install

```sh
docker pull ghcr.io/all-hands-ai/runtime:latest
pip install openhands-ai
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call openhands --task "implement the GET /v1/users endpoint per spec/users.md"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Start a sandboxed runtime container and mount the repo as `WORKSPACE_BASE`.
3. Forward Cortex's plan to `edit_file` / `run_command` / `browser_action` tools.
4. Log every tool call to Chronicle. Trust adjusts by ±0.10 / −0.30 per call.

## Defaults

- Tier: `MONITOR` — sandboxed shell + browser is high blast-radius; nothing escalates without operator review.
- Trust floor: `0.70` — top of the coding category.
- Benchmark: SWE-bench Verified 41.7 (with Claude, as of 2026-03-30).
