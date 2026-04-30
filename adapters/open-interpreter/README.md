# open-interpreter — MCP adapter

Bridges [Open Interpreter](https://openinterpreter.com) into ONEXUS via a thin Python shim.

## Install

```sh
pip install open-interpreter
pip install "onexus-agents-pipeline[adapters]"
```

## Invoke from ONEXUS

```sh
onexus call open-interpreter --task "list every .png larger than 5MB under ~/Downloads and summarize"
```

## Defaults

- Tier: `MONITOR` — every shell or Python invocation is logged before execution.
- Trust floor: `0.7` — higher than coding agents because of host-OS reach.
- `OI_AUTO_RUN` is **off** by default; ONEXUS asks the operator before each command
  unless the operator promotes the agent to `EXECUTOR`.

## Why a shim

Open Interpreter does not expose an MCP server natively today. `server.py`
(written when this adapter is built out) wraps the Open Interpreter library
in `mcp.server.stdio` and surfaces `run_python`, `run_shell`, `read_file`,
and `write_file` as MCP tools.
