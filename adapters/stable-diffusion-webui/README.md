# Stable Diffusion WebUI — MCP adapter

Bridges [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) into ONEXUS via MCP.

## Install

```sh
# 1. Run the WebUI with the REST API enabled (separate process)
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui
cd stable-diffusion-webui
./webui.sh --api --listen --port 7860

# 2. Install the ONEXUS adapter
pip install "onexus-agents-pipeline[adapters]"
```

The adapter does **not** spawn the WebUI — it expects a server already running at `SD_WEBUI_HOST` (default `127.0.0.1:7860`) with `--api` enabled.

## Invoke from ONEXUS

```sh
onexus call stable-diffusion-webui \
  --task "render 'isometric studio, soft northern light, 35mm' at 1024x1024 with sd_xl_base_1.0"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `txt2img` (or `img2img` if a source image is attached).
3. Stream `get_progress` updates back; the operator approves the final image before write-out.

## Defaults

- Tier: `ADVISOR` — outputs are previewed before write-out since image gen burns GPU time and queue space.
- Trust floor: `0.40` — bounded blast radius (writes only to `OUTPUT_DIR`, no shell, no network beyond the WebUI host).
- License: AGPL-3.0 — review before bundling into closed deployments.
