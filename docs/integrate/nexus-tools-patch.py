# ──────────────────────────────────────────────────────────────────────
# NEXUS integration patch — paste these into nexus/mcp/tools.py
#
# Three additions:
#   1. Import the catalog client (top of file with existing imports)
#   2. Three new entries in TOOL_DEFINITIONS
#   3. Three new handler methods + dispatch wiring
#
# This patch is written for NEXUS as of 2026-06-09. The file structure
# may have moved by the time you run this — match by purpose, not
# exact line numbers.
# ──────────────────────────────────────────────────────────────────────


# ── 1. Imports ────────────────────────────────────────────────────────
# At the top of nexus/mcp/tools.py, with the other module imports:

from pipeline.client import OnexusAgentsClient

# Module-level singleton so we don't re-fetch on every tool invocation.
_AGENTS_CLIENT: OnexusAgentsClient | None = None


def _agents_client() -> OnexusAgentsClient:
    """Cached client for the public ONEXUS-Agents catalog.

    HTTP backend by default — works without a local clone. Set the
    NEXUS_AGENTS_CATALOG env var to a clone path for offline mode.
    """
    global _AGENTS_CLIENT
    if _AGENTS_CLIENT is None:
        import os
        local = os.environ.get("NEXUS_AGENTS_CATALOG")
        _AGENTS_CLIENT = (
            OnexusAgentsClient.from_local(local)
            if local
            else OnexusAgentsClient.from_url()
        )
    return _AGENTS_CLIENT


# ── 2. Tool definitions ───────────────────────────────────────────────
# Append these dicts to TOOL_DEFINITIONS:

TOOL_DEFINITIONS_ADDITION = [
    {
        "name": "nexus_agents_browse",
        "description": (
            "Browse the ONEXUS-Agents catalog. Filter by task category, "
            "runnable-via-MCP, or detected framework. Returns up to `limit` "
            "agents ranked by composite score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category slug (coding, web-dev, audio-speech, etc.).",
                },
                "runnable": {
                    "type": "boolean",
                    "description": "If true, only return agents with an MCP adapter.",
                },
                "framework": {
                    "type": "string",
                    "description": "Framework slug (langchain, crewai, mcp, autogen, ...).",
                },
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "nexus_agents_search",
        "description": (
            "Fuzzy text search across agent name, slug, tagline, category, tags. "
            "AND semantics across tokens. Returns up to `limit` matches."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "nexus_agents_info",
        "description": (
            "Full record for one agent including the MCP adapter descriptor "
            "(when present) and the latest composite score / rank."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "slug": {"type": "string"},
            },
            "required": ["category", "slug"],
        },
    },
]
# After defining TOOL_DEFINITIONS_ADDITION, extend the existing list:
#     TOOL_DEFINITIONS.extend(TOOL_DEFINITIONS_ADDITION)


# ── 3. Handler methods ────────────────────────────────────────────────
# Inside the ToolHandlers class (or wherever existing nexus_message,
# nexus_route, nexus_memory_get handlers live), add these methods.
# `_compact_agent` keeps payloads small so the LLM doesn't see noise.


def _compact_agent(agent) -> dict:
    return {
        "slug": agent.slug,
        "name": agent.name,
        "tagline": agent.tagline,
        "category": agent.category,
        "runnable": agent.runnable,
        "adapter_ref": agent.adapter_ref,
        "license": agent.license,
        "stars": agent.metrics.stars,
        "frameworks": agent.metrics.frameworks,
        "composite_score": agent.composite_score,
        "rank_in_category": agent.rank_in_category,
        "source": {
            "github": agent.source.github,
            "huggingface": agent.source.huggingface,
            "homepage": str(agent.source.homepage) if agent.source.homepage else None,
        },
    }


def nexus_agents_browse_handler(args: dict) -> list[dict]:
    """Handler for the nexus_agents_browse tool."""
    agents = _agents_client().list_agents(
        category=args.get("category"),
        runnable=args.get("runnable"),
        framework=args.get("framework"),
    )
    return [_compact_agent(a) for a in agents[: args.get("limit", 50)]]


def nexus_agents_search_handler(args: dict) -> list[dict]:
    agents = _agents_client().search(args["query"], limit=args.get("limit", 20))
    return [_compact_agent(a) for a in agents]


def nexus_agents_info_handler(args: dict) -> dict | None:
    agent = _agents_client().get_agent(args["category"], args["slug"])
    return _compact_agent(agent) if agent else None


# ── 4. Wire into dispatch ─────────────────────────────────────────────
# In whichever switch/map handles tool calls (probably handle_tool_call
# or call_tool_handler in tools.py), add three new cases:
#
#     elif name == "nexus_agents_browse":
#         return nexus_agents_browse_handler(args)
#     elif name == "nexus_agents_search":
#         return nexus_agents_search_handler(args)
#     elif name == "nexus_agents_info":
#         return nexus_agents_info_handler(args)
#
# Match the existing dispatch style — some codebases use a dict,
# some a match statement, some if/elif.
