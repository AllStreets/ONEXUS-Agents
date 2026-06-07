"""Detect which agent framework(s) an entry is built on.

Tier 3 enrichment: derives a list of framework slugs from data we already
have (GitHub topics, HF tags, tagline) plus README content fetched during
the weekly rescan. Zero extra API calls during the nightly; the weekly
pass refines via README.

Each framework has:
  - tag/topic patterns (case-folded, exact match)
  - tagline regex (anchored to word boundaries to avoid e.g. "anthropic" in
    a generic description matching the SDK as a framework)
  - README markers (import statements, config keywords) — used by weekly

Detection is intentionally conservative — false positives pollute the
catalog more than false negatives, since "no framework detected" is a
valid state for native MCP servers, plain HF models, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Framework:
    slug: str
    tag_patterns: frozenset[str]
    tagline_pattern: re.Pattern[str]
    readme_pattern: re.Pattern[str]


FRAMEWORKS: tuple[Framework, ...] = (
    Framework(
        slug="langchain",
        tag_patterns=frozenset({"langchain", "langchain-agent", "langgraph"}),
        tagline_pattern=re.compile(r"\b(?:langchain|langgraph)\b", re.I),
        readme_pattern=re.compile(
            r"(?:from\s+langchain|import\s+langchain|langchain[_-](?:core|community))",
            re.I,
        ),
    ),
    Framework(
        slug="llamaindex",
        tag_patterns=frozenset({"llamaindex", "llama-index", "llama_index"}),
        tagline_pattern=re.compile(r"\bllama[\s-]?index\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+llama_index|import\s+llama_index)", re.I),
    ),
    Framework(
        slug="crewai",
        tag_patterns=frozenset({"crewai", "crew-ai"}),
        tagline_pattern=re.compile(r"\bcrew[\s-]?ai\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+crewai|import\s+crewai|pip\s+install\s+crewai)", re.I),
    ),
    Framework(
        slug="autogen",
        tag_patterns=frozenset({"autogen", "microsoft-autogen", "pyautogen"}),
        tagline_pattern=re.compile(r"\bautogen\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+autogen|import\s+autogen|pyautogen)", re.I),
    ),
    Framework(
        slug="smolagents",
        tag_patterns=frozenset({"smolagents", "smol-agents"}),
        tagline_pattern=re.compile(r"\bsmolagents?\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+smolagents|import\s+smolagents)", re.I),
    ),
    Framework(
        slug="dspy",
        tag_patterns=frozenset({"dspy", "dspy-ai"}),
        tagline_pattern=re.compile(r"\bdspy\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+dspy|import\s+dspy|pip\s+install\s+dspy)", re.I),
    ),
    Framework(
        slug="openai-agents-sdk",
        tag_patterns=frozenset({"openai-agents", "openai-agents-sdk", "agents-sdk"}),
        tagline_pattern=re.compile(r"\bopenai[\s-]agents(?:[\s-]sdk)?\b", re.I),
        readme_pattern=re.compile(
            r"(?:from\s+agents\s+import|from\s+openai_agents|import\s+openai_agents|pip\s+install\s+openai-agents)",
            re.I,
        ),
    ),
    Framework(
        slug="anthropic-sdk",
        tag_patterns=frozenset({"anthropic", "anthropic-sdk", "claude-sdk"}),
        tagline_pattern=re.compile(r"\b(?:claude|anthropic)\s+(?:sdk|api|agent)s?\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+anthropic|import\s+anthropic)", re.I),
    ),
    Framework(
        slug="mcp",
        tag_patterns=frozenset(
            {"mcp", "mcp-server", "mcp-servers", "model-context-protocol", "mcp-client"}
        ),
        tagline_pattern=re.compile(r"\bmodel\s+context\s+protocol\b", re.I),
        readme_pattern=re.compile(
            r'(?:"mcpServers"\s*:|@modelcontextprotocol/|from\s+mcp\b|import\s+mcp\.)',
            re.I,
        ),
    ),
    Framework(
        slug="transformers",
        tag_patterns=frozenset({"transformers", "huggingface-transformers"}),
        tagline_pattern=re.compile(r"\bhugging\s*face\s+transformers\b", re.I),
        readme_pattern=re.compile(
            r"(?:from\s+transformers|import\s+transformers|AutoModel|AutoTokenizer)",
            re.I,
        ),
    ),
    Framework(
        slug="gradio",
        tag_patterns=frozenset({"gradio", "gradio-app"}),
        tagline_pattern=re.compile(r"\bgradio\b", re.I),
        readme_pattern=re.compile(r"(?:from\s+gradio|import\s+gradio|gr\.Interface|gr\.Blocks)", re.I),
    ),
)


def detect_frameworks(
    tags: list[str] | None = None,
    tagline: str | None = None,
    readme: str | None = None,
) -> list[str]:
    """Return sorted list of detected framework slugs. Conservative by design."""
    detected: set[str] = set()
    lowered_tags = {t.lower() for t in (tags or []) if isinstance(t, str)}

    for fw in FRAMEWORKS:
        if lowered_tags & fw.tag_patterns:
            detected.add(fw.slug)
            continue
        if tagline and fw.tagline_pattern.search(tagline):
            detected.add(fw.slug)
            continue
        if readme and fw.readme_pattern.search(readme):
            detected.add(fw.slug)

    return sorted(detected)
