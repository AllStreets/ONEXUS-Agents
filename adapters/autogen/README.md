# AutoGen — MCP adapter

Bridges [AutoGen](https://github.com/microsoft/autogen) into ONEXUS via MCP.

## Install

```sh
pip install "pyautogen>=0.2"
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call autogen \
  --task "stand up a planner+coder group chat to scaffold a FastAPI service with one CRUD route"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Read role definitions from `AUTOGEN_CONFIG` (or build a default planner/coder/critic trio).
3. Drive `run_group_chat` with the task; stream `get_transcript` back as the conversation unfolds.
4. Code-execution agents write to `WORK_DIR`; outputs are surfaced for operator review before commit.

## Defaults

- Tier: `MONITOR` — group chats can recurse and spawn code-execution agents; every turn is observed.
- Trust floor: `0.70` — higher than single-agent coders because the failure mode (runaway loops) is less bounded.
- License: CC-BY-4.0 — fine for internal use; review attribution requirements before public redistribution.
