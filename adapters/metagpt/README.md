# MetaGPT — MCP adapter

Bridges [MetaGPT](https://github.com/FoundationAgents/MetaGPT) into ONEXUS via MCP.

## Install

```sh
pip install metagpt
metagpt --init-config  # writes ~/.metagpt/config2.yaml — fill in API keys
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call metagpt \
  --task "design and implement a CLI todo app with sqlite persistence"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `run_company`, which runs PM → Architect → Engineer → QA in sequence.
3. Each role's output (PRD, system design, code, test report) lands as a separate artifact in `WORKSPACE`.
4. Operator reviews artifacts before any are promoted out of the workspace.

## Defaults

- Tier: `MONITOR` — multi-role pipeline with file-system writes; every artifact is observed.
- Trust floor: `0.70` — like AutoGen, the failure mode (loops between roles, drifting requirements) needs supervision.
- License: MIT.
