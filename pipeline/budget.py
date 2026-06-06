"""Per-run API budget tracker.

Hard caps GitHub/HF call counts so a runaway crawl can't blow past the
free-tier rate windows (GITHUB_TOKEN ≈ 1000/hr non-search + 30/min search;
PAT 5000/hr). Defaults are set to land comfortably inside those windows for
a 60-minute job and can be overridden via env vars.

The crawlers call `budget.spend(kind)` before each API call; if the budget
is exhausted the call returns None and the crawl proceeds without it,
preserving existing on-disk entries via the "missing-agent-preservation"
loop in nightly.main().
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class APIBudget:
    """Counts down API calls per category until the per-run cap is hit."""

    gh_remaining: int
    hf_remaining: int

    def can_spend(self, kind: str) -> bool:
        if kind == "gh":
            return self.gh_remaining > 0
        if kind == "hf":
            return self.hf_remaining > 0
        return True

    def spend(self, kind: str, n: int = 1) -> bool:
        """Decrement and return True if the spend was allowed."""
        if kind == "gh":
            if self.gh_remaining <= 0:
                return False
            self.gh_remaining -= n
            return True
        if kind == "hf":
            if self.hf_remaining <= 0:
                return False
            self.hf_remaining -= n
            return True
        return True


_BUDGET: APIBudget | None = None


def set_budget(b: APIBudget) -> None:
    global _BUDGET
    _BUDGET = b


def get_budget() -> APIBudget:
    """Return the active budget, or a permissive default if unset.

    The default is intentionally huge so unit tests and ad-hoc CLI runs that
    forget to initialize a budget aren't surprised by silent rate-limiting.
    """
    return _BUDGET or APIBudget(gh_remaining=10**9, hf_remaining=10**9)


def from_env() -> APIBudget:
    """Build a budget from env vars with safe defaults.

    GITHUB_TOKEN: 1000/hr non-search + ~1800/hr search → ~12,000 in a 60-min
    job is comfortably under both windows with tenacity backoff.
    GH_PAT (user-supplied): 5000/hr → 30,000 ceiling for 60 min.
    """
    is_pat = bool(os.environ.get("GH_PAT"))
    gh_default = 30_000 if is_pat else 12_000
    hf_default = 5_000

    gh = int(os.environ.get("ONEXUS_GH_BUDGET") or gh_default)
    hf = int(os.environ.get("ONEXUS_HF_BUDGET") or hf_default)
    return APIBudget(gh_remaining=gh, hf_remaining=hf)
