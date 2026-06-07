"""One-shot backfill: every agent with frameworks=["mcp", ...] but
runnable=false gets runnable=true + adapter_ref="mcp/stdio".

Run once after merging fix/mcp-implies-runnable, then delete. Going
forward the same logic runs inline in pipeline.build and
pipeline.weekly so new entries stay consistent without manual passes.
"""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path("catalog")
GENERIC_MCP_ADAPTER = "mcp/stdio"


def main() -> int:
    flipped = 0
    skipped = 0
    for p in CATALOG.rglob("*.json"):
        parts = p.relative_to(CATALOG).parts
        if parts and parts[0].startswith("_"):
            continue
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            print(f"skip {p}: {e}")
            skipped += 1
            continue
        fws = (data.get("metrics") or {}).get("frameworks") or []
        if "mcp" not in fws:
            continue
        if data.get("runnable"):
            continue
        data["runnable"] = True
        if not data.get("adapter_ref"):
            data["adapter_ref"] = GENERIC_MCP_ADAPTER
        p.write_text(json.dumps(data, indent=2) + "\n")
        flipped += 1
    print(f"flipped {flipped} agents to runnable=true (mcp framework was present)")
    print(f"skipped {skipped} unreadable files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
