"""faster-whisper MCP adapter: speech to text on the CPU, with the model baked in.

Runs as a stdio MCP server inside the container described in mcp.json. The Whisper
`base` model is downloaded when the image is built, so at run time it needs no network
at all. Audio arrives base64-encoded in the tool call, because the container sees none
of the operator's files, and is decoded in memory.
"""
from __future__ import annotations

import base64
import binascii
import io
import os
from typing import Any

from faster_whisper import WhisperModel
from mcp.server.fastmcp import FastMCP

MODEL_DIR = os.environ.get("WHISPER_MODEL_DIR", "/models/base")
MAX_AUDIO_BYTES = 25 * 1024 * 1024

mcp = FastMCP("faster-whisper")
_model: WhisperModel | None = None


def model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
    return _model


def _audio(audio_base64: str) -> io.BytesIO:
    try:
        raw = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("audio_base64 is not valid base64") from exc
    if not raw:
        raise ValueError("audio is empty")
    if len(raw) > MAX_AUDIO_BYTES:
        raise ValueError(f"audio is larger than {MAX_AUDIO_BYTES // (1024 * 1024)} MB")
    return io.BytesIO(raw)


def _run(audio_base64: str, task: str, language: str | None) -> tuple[list[dict[str, Any]], Any]:
    segments, info = model().transcribe(_audio(audio_base64), task=task, language=language or None, beam_size=5)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
    return out, info


@mcp.tool()
def transcribe(audio_base64: str, language: str | None = None) -> dict[str, Any]:
    """Transcribe audio (any format FFmpeg reads), given as base64. Language is detected
    unless given as a code like "en"."""
    segs, info = _run(audio_base64, "transcribe", language)
    return {"language": info.language, "duration": round(info.duration, 2), "text": " ".join(s["text"] for s in segs)}


@mcp.tool()
def transcribe_chunked(audio_base64: str, language: str | None = None) -> dict[str, Any]:
    """Like transcribe, but returns each segment with its start and end in seconds."""
    segs, info = _run(audio_base64, "transcribe", language)
    return {"language": info.language, "duration": round(info.duration, 2), "segments": segs}


@mcp.tool()
def detect_language(audio_base64: str) -> dict[str, Any]:
    """The spoken language of the first 30 seconds, and how sure the model is."""
    _, info = model().transcribe(_audio(audio_base64), beam_size=1)
    return {"language": info.language, "probability": round(info.language_probability, 3)}


@mcp.tool()
def translate(audio_base64: str, language: str | None = None) -> dict[str, Any]:
    """Transcribe audio into English text, whatever language is spoken."""
    segs, info = _run(audio_base64, "translate", language)
    return {"source_language": info.language, "text": " ".join(s["text"] for s in segs)}


if __name__ == "__main__":
    mcp.run()
