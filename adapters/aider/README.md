# aider — MCP adapter

Bridges [Aider](https://aider.chat) into ONEXUS via MCP.

## Install

```sh
pip install aider-chat
# stdio MCP shim (this directory's server.py wraps Aider's library API)
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call aider --task "refactor src/auth.py to use jwt.decode"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Mount the current repo as the `repo` resource.
3. Forward Cortex's task plan to `edit_file` / `run_command` tools.
4. Log every tool call to Chronicle and adjust trust by ±0.12 / −0.22.

## Defaults

- Tier: `ADVISOR` — proposes diffs but cannot push without operator approval.
- Trust floor: `0.55` — the agent must clear this before Cortex dispatches it.
- Model: claude-opus-4-7 if `ANTHROPIC_API_KEY` is set; otherwise gpt-4o.
