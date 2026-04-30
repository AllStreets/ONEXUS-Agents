# LangGraph — MCP adapter

Bridges [LangGraph](https://github.com/langchain-ai/langgraph) into ONEXUS via MCP.

## Install

```sh
pip install langgraph "langchain>=0.2"
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call langgraph \
  --task "run the customer-triage graph on ticket #4821"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Discover compiled graphs in `GRAPH_DIR` (any `*.py` exporting a `graph` symbol).
3. Forward Cortex's input to `invoke_graph` (or `stream_graph` for incremental output).
4. Persist checkpoints in `CHECKPOINT_DIR` so long runs can be resumed via `resume_run`.

## Defaults

- Tier: `ADVISOR` — graph topology is operator-defined; node side effects are scoped by what the author wired in.
- Trust floor: `0.55` — lower than open-ended frameworks (AutoGen, MetaGPT) because user-authored graphs have a known shape.
- License: MIT.
