# Catalog seeds

Hand-curated bootstrap lists per category. The daily pipeline reads these
files first, refreshes their metrics from GitHub / Hugging Face, then layers
auto-discovered candidates on top before scoring and truncating to the top 250.

Seeds **do not** bypass ranking — a low-scoring seed will still be displaced
by higher-scoring entrants. Seeds exist so the catalog has a credible starting
state on day one and so high-signal projects with weak topic tagging are
guaranteed to be evaluated.

## Format

```yaml
category: coding
agents:
  - source: github
    repo: Aider-AI/aider
    runnable: true
    adapter_ref: adapters/aider/mcp.json
    notes: "Pair-programming AI in your terminal."

  - source: huggingface
    model: bigcode/starcoder2-15b
    runnable: false
    notes: "Foundation model used by several coding agents."
```

## Fields

- `source` — `github` or `huggingface`
- `repo` — `owner/name` (when source is `github`)
- `model` — `org/model-id` (when source is `huggingface`)
- `runnable` — true if a working MCP adapter exists under `adapters/`
- `adapter_ref` — path to the MCP descriptor (required when `runnable: true`)
- `notes` — one-line tagline for the catalog (the pipeline may refine this)

The pipeline auto-fills `slug`, `tagline`, `tags`, `author`, `license`,
`metrics`, `composite_score`, and `rank_in_category` from upstream APIs.
