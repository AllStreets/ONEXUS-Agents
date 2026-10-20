"""Smoke-test a confined adapter image: start it the way ONEXUS does, speak MCP to it,
and check it offers exactly the tools its mcp.json declares.

    python adapters/smoke.py haystack [image]

The flags match nexus/agents/confine.py: no network, read-only root, private tmpfs,
every capability dropped, no privilege escalation, a non-root user and resource limits.
Standard library only, so CI needs nothing installed to run it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(name: str, image: str | None = None) -> int:
    desc = json.loads((HERE / name / "mcp.json").read_text())
    conf = desc["confinement"]
    image = image or conf["image"]
    argv = [
        "docker", "run", "--rm", "-i", "--network", "none",
        "--read-only", "--tmpfs", "/tmp:rw,size=64m", "--tmpfs", "/work:rw,size=256m", "-w", "/work",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
        "--memory", "1g", "--cpus", "1", "--pids-limit", "256", "-e", "HOME=/work",
        image, conf.get("command") or desc["command"], *desc["args"],
    ]
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for m in msgs:
            proc.stdin.write((json.dumps(m) + "\n").encode())
            proc.stdin.flush()
        tools = None
        while tools is None:
            line = proc.stdout.readline()
            if not line:
                print(proc.stderr.read().decode()[-2000:], file=sys.stderr)
                print(f"FAIL {name}: server exited before listing tools", file=sys.stderr)
                return 1
            msg = json.loads(line)
            if msg.get("id") == 2:
                tools = {t["name"] for t in msg["result"]["tools"]}
    finally:
        proc.kill()
        proc.wait()
    declared = set(desc["capabilities"]["tools"])
    if tools != declared:
        print(f"FAIL {name}: serves {sorted(tools)}, declares {sorted(declared)}", file=sys.stderr)
        return 1
    print(f"OK {name}: {len(tools)} tools, confined, no network")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
