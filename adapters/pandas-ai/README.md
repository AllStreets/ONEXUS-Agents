# PandasAI — MCP adapter

Bridges [PandasAI](https://github.com/gventuri/pandas-ai) into ONEXUS via MCP.

## Install

```sh
pip install pandasai
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call pandas-ai \
  --task "in ./data/sales.csv, what was the median order value per region in Q4?"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Index every tabular file in `DATA_DIR` (CSV / XLSX / Parquet) as a named table.
3. Forward the natural-language question to `ask_directory`; the LLM emits pandas code that runs in a sandboxed exec scope.
4. Return the dataframe / scalar / chart back; `explain_last` exposes the generated code for audit.

## Defaults

- Tier: `ADVISOR` — generated code is sandboxed, but the agent can still read the whole `DATA_DIR`; outputs and code are reviewed before commit.
- Trust floor: `0.50` — moderate; failure modes include bad joins and silent NaN drops.
- License: NOASSERTION on GitHub — review the upstream LICENSE file before redistributing.
