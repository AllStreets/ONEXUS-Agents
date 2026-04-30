# faster-whisper — MCP adapter

Bridges [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) into ONEXUS via MCP.

## Install

```sh
pip install faster-whisper
pip install "onexus-agents-pipeline[adapters]"
```

GPU acceleration (optional):

```sh
pip install "faster-whisper[cuda]"
```

## Invoke from ONEXUS

```sh
onexus call faster-whisper \
  --task "transcribe ./meetings/2026-04-30-standup.m4a with speaker timestamps"
```

ONEXUS will:
1. Launch the MCP server declared in `mcp.json`.
2. Forward Cortex's spec to `transcribe`.
3. Return the transcript inline; long files stream chunk-by-chunk via `transcribe_chunked`.

## Defaults

- Tier: `EXECUTOR` — runs autonomously since it is read-only over audio + sandboxed transcript output.
- Trust floor: `0.30` — local inference, no network, no shell.
- Model: `large-v3` by default; switch to `distil-large-v3` for ~2x speed at near-parity WER.
- Device: auto-detects CUDA, falls back to CPU.
