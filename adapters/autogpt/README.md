# AutoGPT — MCP adapter

Bridges [AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) into ONEXUS via MCP.

## Install

```sh
pip install autogpt
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call autogpt \
  --task "research the top 5 open-source vector DBs and produce a comparison table"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. `spawn_agent` with the task; loop `step_agent` until the agent declares completion or `AUTOGPT_BUDGET_USD` is exceeded.
3. Read final artifacts via `get_workspace_file`.

## Defaults

- Tier: `MONITOR` — autonomous loop with broad capability surface; every step is observed.
- Trust floor: `0.75` — high; recursive planning loops directly burn API spend.
- Cost ceiling: enforced via `AUTOGPT_BUDGET_USD` (default $5) so a runaway loop self-terminates.
- License: NOASSERTION (Polyform Shield variant) — review upstream LICENSE before commercial use.
