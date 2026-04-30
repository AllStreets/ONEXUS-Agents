# ComfyUI — MCP adapter

Bridges [ComfyUI](https://github.com/comfyanonymous/ComfyUI) into ONEXUS via MCP.

## Install

```sh
# 1. Run a ComfyUI server (separate process)
git clone https://github.com/comfyanonymous/ComfyUI && cd ComfyUI
pip install -r requirements.txt
python main.py --listen 127.0.0.1 --port 8188

# 2. Install the ONEXUS adapter
pip install "onexus-agents-pipeline[adapters]"
```

The adapter does **not** spawn ComfyUI — it expects a server already running at `COMFYUI_HOST` (default `127.0.0.1:8188`).

## Invoke from ONEXUS

```sh
onexus call comfyui \
  --task "render workflow flux-dev.json with prompt 'isometric studio, soft northern light'"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `run_workflow` (resolves the JSON graph from `WORKFLOW_DIR`).
3. Stream queue progress back; the operator approves the final image before write-out.

## Defaults

- Tier: `ADVISOR` — outputs are previewed before write-out since image gen burns GPU time.
- Trust floor: `0.40` — bounded blast radius (writes only to `OUTPUT_DIR`, no shell, no network).
- Server: defaults to `127.0.0.1:8188`; override with `COMFYUI_HOST` or `COMFYUI_API_BASE`.
- License: GPL-3.0 — review before bundling into closed deployments.
