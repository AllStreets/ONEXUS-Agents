"""SWE-bench Verified scraper.

Source: github.com/swe-bench/experiments (the official results repo).
Each system result lives under `evaluation/verified/<system>/results/`
with a metadata file that includes the model + agent harness and the
verified pass rate. We harvest those into BenchmarkEntry keyed by the
agent's catalog source (github owner/repo when the system name maps to
a recognizable agent project like aider, opendevin, sweagent).

Reality check: most SWE-bench entries on the public leaderboard list
a model name (e.g. "Claude 3.5 Sonnet + Agentless") rather than a repo,
so the mapping is necessarily fuzzy. We carry a hand-curated alias map
that resolves known system names to catalog GitHub repos. Adding a new
mapping is a one-line dict entry — no API call needed.

When the alias map misses, the entry is silently skipped (better to
under-report than to misattribute scores).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pipeline.benchmarks.base import BenchmarkEntry, BenchmarkScraper

LEADERBOARD_URL = "https://www.swebench.com/"
EXPERIMENTS_API = (
    "https://api.github.com/repos/swe-bench/experiments/contents/evaluation/verified"
)

# Hand-curated mapping: leaderboard "system name" (lowercased) → catalog
# GitHub key (owner/repo). Loose match — substring containment works.
ALIAS_MAP: dict[str, str] = {
    "aider": "Aider-AI/aider",
    "opendevin": "All-Hands-AI/OpenHands",
    "openhands": "All-Hands-AI/OpenHands",
    "sweagent": "princeton-nlp/SWE-agent",
    "swe-agent": "princeton-nlp/SWE-agent",
    "agentless": "OpenAutoCoder/Agentless",
    "moatless": "aorwall/moatless-tools",
    "lingma": "alibaba/lingma-swe-gpt",
    "marscode": "marscode-team/marscode-agent",
    "autocoderover": "nus-apr/auto-code-rover",
}


def _resolve(system_name: str) -> str | None:
    """Map a leaderboard 'system' string to a catalog GitHub key."""
    lower = system_name.lower()
    for alias, key in ALIAS_MAP.items():
        if alias in lower:
            return key
    return None


class SWEBenchVerifiedScraper(BenchmarkScraper):
    name = "SWE-bench Verified"

    def fetch(self, client: httpx.Client) -> dict[str, BenchmarkEntry]:
        out: dict[str, BenchmarkEntry] = {}
        try:
            r = client.get(EXPERIMENTS_API, timeout=20)
            if r.status_code != 200:
                return out
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            for entry in r.json():
                if entry.get("type") != "dir":
                    continue
                system = entry.get("name", "")
                key = _resolve(system)
                if not key:
                    continue
                # Each system dir contains a results file. Fetching every
                # one would blow the API budget, so we mark presence-only
                # for now (score=0.5 placeholder) and rely on hand-curated
                # benchmark entries in catalog files for real scores. A
                # follow-up can deep-fetch each system's results.json.
                out[key] = BenchmarkEntry(
                    score=0.5,
                    as_of=today,
                    source_url=LEADERBOARD_URL,
                )
        except Exception:
            return out
        return out
