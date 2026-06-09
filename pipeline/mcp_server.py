"""MCP server exposing the ONEXUS-Agents catalog.

Implements the three tools described in the ONEXUS README:

  nexus_agents_browse(category=None, runnable=None, framework=None, limit=50)
      → paginated list of agents, score-sorted

  nexus_agents_search(query, limit=20)
      → fuzzy text search across name, slug, tagline, category, tags

  nexus_agents_info(category, slug)
      → full agent record + MCP adapter descriptor when present

ONEXUS Cortex registers this server as one of its MCP sources; the tools
become part of its dispatch repertoire automatically.

Run standalone via:

    uv run python -m pipeline.mcp_server --local /path/to/ONEXUS-Agents
    # or
    uv run python -m pipeline.mcp_server --url https://onexus-agents.vercel.app
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from pipeline.client import DEFAULT_BASE_URL, OnexusAgentsClient


def _agent_dict(agent) -> dict:
    """Compact dict for tool responses — keeps payloads small for LLMs."""
    return {
        "slug": agent.slug,
        "name": agent.name,
        "tagline": agent.tagline,
        "category": agent.category,
        "tags": agent.tags,
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


async def serve(client: OnexusAgentsClient) -> None:
    """Wire the client into a stdio MCP server and run forever.

    The `mcp` package is imported lazily so the rest of pipeline/ stays
    free of the dependency. Install with `pip install -e ".[mcp]"`.
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        sys.exit("missing `mcp` package — install with: pip install -e \".[mcp]\"")

    server: Server = Server("onexus-agents")

    @server.list_tools()
    async def _list_tools() -> list[Tool]:  # noqa: D401
        return [
            Tool(
                name="nexus_agents_browse",
                description=(
                    "List agents from the catalog, optionally filtered by category, runnable flag, "
                    "or framework. Returns up to `limit` agents ranked by composite score."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Category slug (e.g. 'coding', 'web-dev')."},
                        "runnable": {"type": "boolean", "description": "If true, return only runnable agents."},
                        "framework": {"type": "string", "description": "Framework slug (e.g. 'langchain', 'mcp')."},
                        "limit": {"type": "integer", "default": 50},
                    },
                },
            ),
            Tool(
                name="nexus_agents_search",
                description="Fuzzy text search across agent name, slug, tagline, category, tags.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="nexus_agents_info",
                description="Full record for one agent including the MCP adapter descriptor when present.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "slug": {"type": "string"},
                    },
                    "required": ["category", "slug"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, args: dict) -> list[TextContent]:
        if name == "nexus_agents_browse":
            agents = client.list_agents(
                category=args.get("category"),
                runnable=args.get("runnable"),
                framework=args.get("framework"),
            )[: args.get("limit", 50)]
            payload = [_agent_dict(a) for a in agents]
        elif name == "nexus_agents_search":
            agents = client.search(args["query"], limit=args.get("limit", 20))
            payload = [_agent_dict(a) for a in agents]
        elif name == "nexus_agents_info":
            agent = client.get_agent(args["category"], args["slug"])
            payload = _agent_dict(agent) if agent else None
        else:
            return [TextContent(type="text", text=f"unknown tool: {name}")]
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="ONEXUS-Agents MCP server (stdio).")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--local", help="Path to a local ONEXUS-Agents clone")
    src.add_argument("--url", default=DEFAULT_BASE_URL, help="Site URL (default: production)")
    args = parser.parse_args()

    client = (
        OnexusAgentsClient.from_local(args.local)
        if args.local
        else OnexusAgentsClient.from_url(args.url)
    )
    asyncio.run(serve(client))


if __name__ == "__main__":
    main()
