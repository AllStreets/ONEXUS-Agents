# Haystack: MCP adapter

Runs [Haystack](https://github.com/deepset-ai/haystack) in ONEXUS as a keyword-search agent: you hand it documents, it ranks passages against a query with BM25. No model, no API key, no network.

It runs **confined**. ONEXUS starts it in the container from this folder's `Dockerfile` with no network, a read-only root, every capability dropped and a non-root user (see `confinement` in `mcp.json` and `nexus/agents/confine.py` in ONEXUS). It sees none of your files, so documents arrive through the tool call.

## Tools

- `index_documents(documents, split=True)`: strings or `{content, meta}`; long ones are split into 200-word passages
- `search(query, top_k=5)`: the best-matching passages with their BM25 scores
- `list_pipelines`, `describe_pipeline(name)`, `run_pipeline(name, inputs)`: the two pipelines behind those tools, `search` and `split-and-index`, as Haystack pipelines

The store lives in memory for as long as the agent runs.

## Build the image

```sh
docker build -t ghcr.io/allstreets/onexus-adapter-haystack:0.1.0 adapters/haystack
python3 adapters/smoke.py haystack
```

`requirements.txt` is the locked set, resolved in the image's base; `requirements.in` is what it was resolved from.

## Defaults

- Tier: `ADVISOR`. It returns passages and changes nothing outside its own store.
- Trust floor: `0.45`.
- License: Apache-2.0.
