# continue — MCP adapter

Bridges [Continue](https://continue.dev) into ONEXUS via MCP.

## Install

```sh
pip install continuedev
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call continue --task "add input validation to handlers/auth.py"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Mount the current repo as the `repo` resource.
3. Forward Cortex's task plan to `edit_file` / `explain_code` tools.
4. Log every tool call to Chronicle and adjust trust by ±0.10 / −0.20.

## Defaults

- Tier: `ADVISOR` — proposes diffs, never auto-pushes.
- Trust floor: `0.55`.
- Model: routes through whichever provider key is present (`ANTHROPIC_API_KEY` preferred).
