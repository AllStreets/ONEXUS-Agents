# gpt-engineer — MCP adapter

Bridges [gpt-engineer](https://github.com/AntonOsika/gpt-engineer) into ONEXUS via MCP.

## Install

```sh
pip install gpt-engineer
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call gpt-engineer --task "scaffold a FastAPI service with JWT auth and a Postgres user model"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `scaffold_project`.
3. Collect generated files for operator review before write-out (ADVISOR tier).

## Defaults

- Tier: `ADVISOR` — best for greenfield scaffolding; reviewed before write.
- Trust floor: `0.50` — low because outputs are bounded to fresh files.
- Model: `gpt-4o` by default; override with `MODEL_NAME`.
