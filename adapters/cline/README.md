# cline — MCP adapter

Bridges [Cline](https://github.com/cline/cline) into ONEXUS via MCP.

## Install

```sh
npm install -g cline
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call cline --task "diagnose the failing test in tests/api/auth_test.py and fix it"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Mount the repo (and a Playwright browser session if requested) as resources.
3. Forward Cortex's plan to `edit_file` / `run_command` / `browser_action` tools.
4. Log every tool call to Chronicle and adjust trust by ±0.10 / −0.30.

## Defaults

- Tier: `MONITOR` — broader capability surface than ADVISOR-tier coders, so every tool call is observed before completion.
- Trust floor: `0.65`.
- Model: Claude (preferred) via `ANTHROPIC_API_KEY`, otherwise OpenAI.
