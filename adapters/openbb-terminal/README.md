# OpenBB Terminal — MCP adapter

Bridges [OpenBB](https://github.com/OpenBB-finance/OpenBBTerminal) into ONEXUS via MCP through the OpenBB Platform Python SDK.

## Install

```sh
pip install openbb
pip install "onexus-agents-pipeline[adapters]"

# Optional: log in to enable credentialed providers (FMP, Polygon, Benzinga, etc.)
python -c "from openbb import obb; obb.account.login(pat='<your OPENBB_PAT>')"
```

## Invoke from ONEXUS

```sh
onexus call openbb-terminal \
  --task "pull AAPL daily closes for the past year and the latest options chain"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Route to the relevant typed tool (`equity_historical`, `options_chain`, `economy_indicator`, …).
3. Honour `OPENBB_PROVIDER_PREFERENCES` for which data provider to hit per asset class.
4. Write any exported tables / charts to `EXPORT_DIR`; preview before commit.

## Defaults

- Tier: `ADVISOR` — read-only surface, but data fetches consume provider quotas; outputs are previewed.
- Trust floor: `0.40` — bounded blast radius (no shell, no writes outside `EXPORT_DIR`), but provider keys may carry billing weight.
- License: OpenBB Terminal CLI is AGPL-3.0; the Platform SDK is MIT — verify the LICENSE in your installed version before bundling into closed deployments.
