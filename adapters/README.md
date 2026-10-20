# Adapters

Each subdirectory bridges a single catalogued agent into ONEXUS via the
[Model Context Protocol](https://modelcontextprotocol.io). An entry in `catalog/`
becomes "runnable" by adding `runnable: true` and `adapter_ref: adapters/<name>/mcp.json`
to its JSON file.

## Layout per adapter

```
adapters/<name>/
  mcp.json    # MCP server descriptor — command, args, env, capabilities
  README.md   # one-line install + one-line invocation
```

## mcp.json shape

```json
{
  "name": "aider",
  "version": "0.1.0",
  "transport": "stdio",
  "command": "aider-mcp",
  "args": [],
  "env": {
    "OPENAI_API_KEY": { "required": true, "description": "Model API key." }
  },
  "capabilities": {
    "tools": ["edit_file", "run_tests", "git_commit"],
    "resources": ["repo"]
  },
  "trust_floor": 0.55,
  "default_tier": "ADVISOR"
}
```

- `transport` — `stdio` or `sse`. Most agents speak stdio.
- `command` / `args` — what ONEXUS launches when Cortex selects this agent.
- `env` — keys the host must provide; declared so ONEXUS can prompt or fail loudly.
- `capabilities` — declared tool/resource names. ONEXUS uses this for permission gating.
- `trust_floor` — minimum trust level required before the agent is dispatched.
- `default_tier` — initial autonomy tier (OBSERVER / ADVISOR / MONITOR / EXECUTOR / AUTONOMOUS).

## Adapter shim (escape hatch)

Some agents don't speak MCP yet. For those, write a thin Python wrapper under
`adapters/<name>/server.py` that exposes the agent's CLI / library through an
`mcp.server` stdio loop, and point `command` at `python -m adapters.<name>.server`.

The intent is MCP-first; the shim is for the long tail.

Today only `haystack` and `faster-whisper` ship their shim. The other descriptors that point at
`python -m adapters.<name>.server` describe a server that hasn't been written yet, so they won't
start until it is.

## Confinement

An adapter can declare a container to run in:

```json
"confinement": { "image": "ghcr.io/allstreets/onexus-adapter-haystack:0.1.0", "command": "python" }
```

ONEXUS then runs it with no network (or, if `hosts` are listed, only those hosts through an egress
proxy), a read-only root, every capability dropped and a non-root user, and records in its ledger
that the launch was confined. Put the `Dockerfile` beside `mcp.json`, lock its dependencies in
`requirements.txt`, and check it with `python3 adapters/smoke.py <name>`, which starts the image
with the same flags and compares the tools it serves to the ones `mcp.json` declares.
Confined today: `haystack` and `faster-whisper`.

## Trust contract

Every adapter is reviewed before merging — both for what it claims it can do and
for what it actually does once installed. Agents that exceed their declared
capabilities are ejected from the runnable set immediately and their adapter is
archived under `adapters/_archive/<name>/` with the violation noted.
