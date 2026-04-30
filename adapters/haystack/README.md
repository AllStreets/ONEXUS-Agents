# Haystack — MCP adapter

Bridges [Haystack](https://github.com/deepset-ai/haystack) into ONEXUS via MCP.

## Install

```sh
pip install "haystack-ai>=2.0"
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call haystack \
  --task "run the support-rag pipeline against 'how do I rotate a service account key?'"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Discover pipelines in `PIPELINE_DIR` (each YAML defines a named pipeline).
3. Forward Cortex's input to `run_pipeline`; index new sources via `index_documents`.
4. Return generated answers + citations; `describe_pipeline` exposes the component graph for audit.

## Defaults

- Tier: `ADVISOR` — pipelines are operator-defined; side effects scoped by wired components.
- Trust floor: `0.45` — moderate; tool-augmented generators can act, but topology constrains them.
- License: Apache-2.0.
