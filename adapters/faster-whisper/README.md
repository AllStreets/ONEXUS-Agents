# faster-whisper: MCP adapter

Runs [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) in ONEXUS for speech to text, on the CPU with int8. The Whisper `base` model is downloaded when the image is built, so the running agent needs no network.

It runs **confined**. ONEXUS starts it in the container from this folder's `Dockerfile` with no network, a read-only root, every capability dropped and a non-root user (see `confinement` in `mcp.json` and `nexus/agents/confine.py` in ONEXUS). It sees none of your files, so audio arrives base64-encoded in the tool call, up to 25 MB, in any format FFmpeg reads.

## Tools

- `transcribe(audio_base64, language=None)`: the text, the detected language and the duration
- `transcribe_chunked(audio_base64, language=None)`: each segment with its start and end in seconds
- `detect_language(audio_base64)`: the language of the first 30 seconds, with the model's confidence
- `translate(audio_base64)`: English text, whatever language is spoken

## Build the image

```sh
docker build -t ghcr.io/allstreets/onexus-adapter-faster-whisper:0.1.0 adapters/faster-whisper
python3 adapters/smoke.py faster-whisper
```

`requirements.txt` is the locked set, resolved in the image's base. PyAV is held at 14.2.0 because 15 and later removed an argument faster-whisper 1.2 still passes.

## Defaults

- Tier: `EXECUTOR` with a trust floor of `0.30`. Its only output is text.
- Model: `base`. Larger models need more memory than the default 1 GB container limit.
