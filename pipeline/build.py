"""Build catalog entries from seed + crawler data."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pipeline.crawlers import github as gh
from pipeline.crawlers import huggingface as hf
from pipeline.schema import Agent, Author, Metrics, Source

UTC_NOW = lambda: datetime.now(UTC)  # noqa: E731

# Topic/tag values that strongly indicate the repo IS an MCP server we can
# speak to over stdio (vs. a client of MCP, or a wrapper that uses the term).
# Author-declared, so false positives stay near zero.
MCP_SERVER_SIGNALS = frozenset({"mcp-server", "mcp-servers", "model-context-protocol"})
GENERIC_MCP_ADAPTER = "mcp/stdio"


def detect_mcp_runnability(tags: list[str]) -> tuple[bool, str | None]:
    """Return (runnable, adapter_ref) if tags declare an MCP server."""
    lowered = {t.lower() for t in tags if isinstance(t, str)}
    if lowered & MCP_SERVER_SIGNALS:
        return True, GENERIC_MCP_ADAPTER
    return False, None


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:64] or "agent"


def build_from_github(
    client,
    repo_full_name: str,
    category: str,
    *,
    runnable: bool = False,
    adapter_ref: str | None = None,
    notes: str | None = None,
    discovered_via: str = "auto",
    existing_first_seen: datetime | None = None,
) -> Agent | None:
    meta = gh.fetch_repo(client, repo_full_name)
    if not meta:
        return None
    owner, name = repo_full_name.split("/", 1)
    slug = slugify(name)
    if not runnable:
        auto_runnable, auto_adapter = detect_mcp_runnability(meta["topics"])
        if auto_runnable:
            runnable = True
            if adapter_ref is None:
                adapter_ref = auto_adapter
    return Agent(
        slug=slug,
        name=name,
        tagline=(notes or meta["description"] or name)[:200],
        category=category,
        tags=meta["topics"][:10],
        author=Author(
            type="org" if meta["owner_type"] == "organization" else "user",
            handle=owner,
            url=meta["owner_html_url"] or f"https://github.com/{owner}",
        ),
        source=Source(
            primary="github",
            github=repo_full_name,
            huggingface=None,
            homepage=meta["homepage"] if meta["homepage"] else None,
        ),
        license=meta["license"] or "Unknown",
        metrics=Metrics(
            stars=meta["stars"],
            downloads_30d=None,
            last_commit_at=meta["last_commit_at"],
            first_commit_at=meta["first_commit_at"],
        ),
        benchmarks=[],
        runnable=runnable,
        adapter_ref=adapter_ref,
        composite_score=0.0,
        rank_in_category=999,
        discovered_via=discovered_via,
        first_seen_at=existing_first_seen or UTC_NOW(),
        last_refreshed_at=UTC_NOW(),
    )


def build_from_huggingface(
    client,
    model_id: str,
    category: str,
    *,
    runnable: bool = False,
    adapter_ref: str | None = None,
    notes: str | None = None,
    discovered_via: str = "auto",
    existing_first_seen: datetime | None = None,
) -> Agent | None:
    meta = hf.fetch_model(client, model_id)
    if not meta:
        return None
    owner, name = model_id.split("/", 1) if "/" in model_id else ("huggingface", model_id)
    slug = slugify(name)
    if not runnable:
        auto_runnable, auto_adapter = detect_mcp_runnability(meta["tags"])
        if auto_runnable:
            runnable = True
            if adapter_ref is None:
                adapter_ref = auto_adapter
    return Agent(
        slug=slug,
        name=name,
        tagline=(notes or f"{model_id} — {meta.get('pipeline_tag', '')}")[:200],
        category=category,
        tags=[t for t in meta["tags"] if isinstance(t, str)][:10],
        author=Author(
            type="org" if "/" in model_id else "user",
            handle=owner,
            url=f"https://huggingface.co/{owner}",
        ),
        source=Source(
            primary="huggingface",
            github=None,
            huggingface=model_id,
            homepage=None,
        ),
        license=meta["license"],
        metrics=Metrics(
            stars=meta["stars"],
            downloads_30d=meta["downloads_30d"],
            last_commit_at=meta["last_commit_at"],
            first_commit_at=meta["first_commit_at"],
        ),
        benchmarks=[],
        runnable=runnable,
        adapter_ref=adapter_ref,
        composite_score=0.0,
        rank_in_category=999,
        discovered_via=discovered_via,
        first_seen_at=existing_first_seen or UTC_NOW(),
        last_refreshed_at=UTC_NOW(),
    )


def merge_benchmarks(target: Agent, prior: Agent | None) -> None:
    """Carry forward existing benchmark scores when refreshing an existing entry."""
    if prior and prior.benchmarks and not target.benchmarks:
        target.benchmarks = list(prior.benchmarks)


def merge_overrides(target: Agent, prior: Agent | None) -> None:
    """Carry forward runnable + adapter_ref from a prior on-disk entry.

    These fields are set by hand (or via seeds) and must survive auto-discovery
    rebuilds. Without this, an agent that was flipped to runnable=true via a
    catalog edit (without a corresponding seeds.yaml entry) would lose the flag
    the next time _discover rebuilt it via build_from_github.

    Seeds always pass explicit runnable/adapter_ref values, so they win on tie.
    """
    if not prior:
        return
    if not target.runnable and prior.runnable:
        target.runnable = True
    if target.adapter_ref is None and prior.adapter_ref is not None:
        target.adapter_ref = prior.adapter_ref
