"""Read-only client for the ONEXUS-Agents catalog.

Built for downstream consumers (ONEXUS, SMADP, anything else) to access
the catalog without re-implementing fetch + parse logic. Returns typed
Agent / Category objects from pipeline.schema so consumers get the full
Pydantic guarantees the producer side enforces.

Two backends:
  - HTTP (default): fetches search-index.json once then resolves
    individual agents on demand. Cached in memory. Good for processes
    that want fresh data without bundling the catalog.
  - Local: reads from a git clone or local filesystem path. Zero
    network. Good for ONEXUS daemons that bundle the catalog or for
    SMADP-style batch jobs.

Example:

    from pipeline.client import OnexusAgentsClient

    # ONEXUS-style: fetch over HTTP, cache locally
    c = OnexusAgentsClient.from_url()
    coding_agents = c.list_agents(category="coding", runnable=True)
    aider = c.get_agent("coding", "aider")
    matches = c.search("langchain rag")

    # SMADP-style: walk a local clone
    c = OnexusAgentsClient.from_local("/path/to/ONEXUS-Agents")
    for a in c.runnable_only():
        smadp_profile = convert_to_smadp(a)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from pipeline.schema import Agent

DEFAULT_BASE_URL = "https://onexus-agents.vercel.app"
DEFAULT_TTL = 3600  # 1 hour — catalog updates daily, this is comfortable


class OnexusAgentsClient:
    """Read-only client for the catalog. Use OnexusAgentsClient.from_url()
    or .from_local() — direct __init__ is intentionally bare-bones.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        local_path: Path | None = None,
        cache_ttl: int = DEFAULT_TTL,
    ) -> None:
        if (base_url is None) == (local_path is None):
            raise ValueError("supply exactly one of base_url or local_path")
        self.base_url = base_url.rstrip("/") if base_url else None
        self.local_path = local_path
        self.cache_ttl = cache_ttl
        self._index_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._agent_cache: dict[tuple[str, str], Agent] = {}
        self._http = httpx.Client(timeout=15) if base_url else None

    @classmethod
    def from_url(cls, base_url: str = DEFAULT_BASE_URL, **kw: Any) -> OnexusAgentsClient:
        return cls(base_url=base_url, **kw)

    @classmethod
    def from_local(cls, path: str | Path, **kw: Any) -> OnexusAgentsClient:
        p = Path(path)
        if not (p / "catalog").is_dir():
            raise ValueError(f"{p} does not look like an ONEXUS-Agents clone (no catalog/)")
        return cls(local_path=p, **kw)

    # ── public API ─────────────────────────────────────────────────────

    def list_agents(
        self,
        *,
        category: str | None = None,
        runnable: bool | None = None,
        framework: str | None = None,
        benchmarked: bool | None = None,
    ) -> list[Agent]:
        """Filterable list of agents. Multiple filters AND together."""
        if self.local_path:
            agents = list(self._iter_local_agents())
        else:
            idx = self._fetch_index()
            agents = [self._agent_from_index_entry(e) for e in idx]
            agents = [a for a in agents if a is not None]

        def keep(a: Agent) -> bool:
            if category is not None and a.category != category:
                return False
            if runnable is not None and a.runnable != runnable:
                return False
            if framework is not None and framework not in (a.metrics.frameworks or []):
                return False
            if benchmarked is not None and bool(a.benchmarks) != benchmarked:
                return False
            return True

        out = [a for a in agents if keep(a)]
        out.sort(key=lambda a: a.composite_score, reverse=True)
        return out

    def get_agent(self, category: str, slug: str) -> Agent | None:
        """Return the full Agent for a (category, slug), or None if missing."""
        key = (category, slug)
        if key in self._agent_cache:
            return self._agent_cache[key]
        if self.local_path:
            path = self.local_path / "catalog" / category / f"{slug}.json"
            if not path.exists():
                return None
            agent = Agent.model_validate_json(path.read_text())
        else:
            url = f"https://raw.githubusercontent.com/AllStreets/ONEXUS-Agents/main/catalog/{category}/{slug}.json"
            assert self._http is not None
            r = self._http.get(url)
            if r.status_code != 200:
                return None
            agent = Agent.model_validate_json(r.text)
        self._agent_cache[key] = agent
        return agent

    def search(self, query: str, *, limit: int = 50) -> list[Agent]:
        """Fuzzy text search against name, slug, tagline, category, tags.

        Tokenized AND match — every token must hit at least one field.
        Score by prefix-match in name + composite_score as tiebreaker.
        """
        tokens = [t.lower() for t in query.split() if t]
        if not tokens:
            return []
        candidates = self.list_agents()
        scored: list[tuple[float, Agent]] = []
        for a in candidates:
            haystacks = [
                a.name.lower(),
                a.slug.lower(),
                (a.tagline or "").lower(),
                a.category.lower(),
                " ".join(a.tags).lower(),
            ]
            score = 0.0
            hit_all = True
            for tok in tokens:
                local_hit = False
                for h in haystacks:
                    pos = h.find(tok)
                    if pos == -1:
                        continue
                    local_hit = True
                    score += 3 if pos == 0 else 1
                if not local_hit:
                    hit_all = False
                    break
            if hit_all:
                scored.append((score + a.composite_score, a))
        scored.sort(key=lambda x: -x[0])
        return [a for _, a in scored[:limit]]

    def runnable_only(self) -> list[Agent]:
        """All runnable agents, ranked by composite score."""
        return self.list_agents(runnable=True)

    def by_framework(self, framework: str) -> list[Agent]:
        """All agents detected as using the given framework slug
        (langchain, crewai, mcp, autogen, smolagents, dspy,
        openai-agents-sdk, anthropic-sdk, transformers, gradio,
        llamaindex)."""
        return self.list_agents(framework=framework)

    def categories(self) -> list[str]:
        """All category slugs known to the catalog, sorted."""
        if self.local_path:
            cat_dir = self.local_path / "catalog"
            return sorted(
                d.name for d in cat_dir.iterdir()
                if d.is_dir() and not d.name.startswith("_")
            )
        # HTTP fallback — derive from index
        idx = self._fetch_index()
        return sorted({e["category"] for e in idx})

    # ── internals ──────────────────────────────────────────────────────

    def _fetch_index(self) -> list[dict[str, Any]]:
        if self._index_cache is not None:
            ts, data = self._index_cache
            if time.monotonic() - ts < self.cache_ttl:
                return data
        assert self._http is not None and self.base_url is not None
        r = self._http.get(f"{self.base_url}/search-index.json")
        r.raise_for_status()
        data = r.json().get("agents", [])
        self._index_cache = (time.monotonic(), data)
        return data

    def _agent_from_index_entry(self, entry: dict[str, Any]) -> Agent | None:
        # The index entry is compact (no full metrics). Fetch full agent
        # JSON for richer queries.
        return self.get_agent(entry["category"], entry["slug"])

    def _iter_local_agents(self):
        assert self.local_path is not None
        cat_dir = self.local_path / "catalog"
        for d in cat_dir.iterdir():
            if not d.is_dir() or d.name.startswith("_"):
                continue
            for f in d.glob("*.json"):
                try:
                    yield Agent.model_validate_json(f.read_text())
                except Exception:
                    continue
