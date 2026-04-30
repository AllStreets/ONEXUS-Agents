# Unstructured — MCP adapter

Bridges [Unstructured](https://github.com/Unstructured-IO/unstructured) into ONEXUS via MCP.

## Install

```sh
# Local mode (open-source library, no API key)
pip install "unstructured[all-docs]"
pip install "onexus-agents-pipeline[adapters]"

# Or use the hosted API: set UNSTRUCTURED_API_KEY and UNSTRUCTURED_API_URL
```

System dependencies: `libmagic`, `poppler`, `tesseract`, `libreoffice`. See the upstream README for OS-specific install steps.

## Invoke from ONEXUS

```sh
onexus call unstructured \
  --task "partition ./inbox/contract.pdf and chunk for the RAG indexer"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Route to `partition_file` / `partition_directory`; pipe through `chunk_elements` if requested.
3. Write structured JSON to `OUTPUT_DIR`, ready for `stage_for_indexing` into a vector store.

## Defaults

- Tier: `EXECUTOR` — bounded blast radius when running locally.
- Trust floor: `0.30` — low because failure mode is "missed elements," not escalation.
- Hosted mode: setting `UNSTRUCTURED_API_KEY` ships document content to the Unstructured API — confirm residency before enabling.
- License: Apache-2.0.
