# Marker — MCP adapter

Bridges [Marker](https://github.com/VikParuchuri/marker) into ONEXUS via MCP.

## Install

```sh
pip install marker-pdf
pip install "onexus-agents-pipeline[adapters]"
```

GPU optional but strongly recommended — CPU-only conversion is ~10× slower.

## Invoke from ONEXUS

```sh
onexus call marker \
  --task "convert ./inbox/whitepaper.pdf to markdown for the RAG indexer"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward the input path to `convert_pdf` (or `convert_batch` for a directory).
3. Write `<name>.md` plus extracted figures into `OUTPUT_DIR`.

## Defaults

- Tier: `EXECUTOR` — bounded blast radius (filesystem only, no shell, no network). Output is deterministic given the same model + input.
- Trust floor: `0.30` — low because the failure mode is "garbled text," not data loss or escalation.
- License: GPL-3.0 — review before bundling into closed deployments.
