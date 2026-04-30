"""Hugging Face model + space metadata fetcher."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

HF_API = "https://huggingface.co/api"


def _headers() -> dict[str, str]:
    h = {"User-Agent": "onexus-agents-pipeline/0.1"}
    token = os.environ.get("HF_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_model(client: httpx.Client, model_id: str) -> dict[str, Any] | None:
    r = client.get(f"{HF_API}/models/{model_id}", headers=_headers(), timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    return {
        "stars": data.get("likes"),
        "downloads_30d": data.get("downloads"),
        "license": _extract_license(data),
        "last_commit_at": _parse_dt(data.get("lastModified")),
        "first_commit_at": _parse_dt(data.get("createdAt")),
        "tags": data.get("tags") or [],
        "html_url": f"https://huggingface.co/{model_id}",
        "pipeline_tag": data.get("pipeline_tag"),
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def search_models(
    client: httpx.Client, tags: list[str], limit: int = 30
) -> list[str]:
    r = client.get(
        f"{HF_API}/models",
        headers=_headers(),
        params={
            "filter": ",".join(tags),
            "sort": "downloads",
            "direction": -1,
            "limit": limit,
        },
        timeout=20,
    )
    r.raise_for_status()
    return [m["id"] for m in r.json()]


def _extract_license(data: dict) -> str:
    cardData = data.get("cardData") or {}
    lic = cardData.get("license") or "Unknown"
    if isinstance(lic, list):
        lic = lic[0] if lic else "Unknown"
    return str(lic)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
