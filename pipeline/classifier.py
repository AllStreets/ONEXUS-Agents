"""Category classifier — keyword heuristic with optional Claude Haiku fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pipeline.schema import CategoryIndex


@dataclass
class Classification:
    category: str | None
    confidence: float
    reason: str


def classify_keyword(
    text: str, categories: CategoryIndex, threshold: int = 2
) -> Classification:
    """Score every category by keyword hits; pick the winner if it clears the threshold."""
    hay = text.lower()
    best_cat: str | None = None
    best_hits = 0
    for c in categories.categories:
        hits = sum(1 for kw in c.seed_keywords if kw.lower() in hay)
        if hits > best_hits:
            best_cat = c.slug
            best_hits = hits
    if best_hits >= threshold and best_cat:
        return Classification(best_cat, min(1.0, best_hits / 5), "keyword")
    return Classification(None, 0.0, "keyword: below threshold")


def classify_llm(text: str, categories: CategoryIndex) -> Classification:
    """Fallback: ask Claude Haiku to pick a category. Cheap + bounded output."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return Classification(None, 0.0, "llm: no ANTHROPIC_API_KEY set")
    try:
        from anthropic import Anthropic
    except ImportError:
        return Classification(None, 0.0, "llm: anthropic not installed")

    slugs = [c.slug for c in categories.categories]
    catalog_lines = "\n".join(f"- {c.slug}: {c.description}" for c in categories.categories)

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        system=(
            "You classify open-source AI agents into a single category slug. "
            "Reply with ONLY the slug, nothing else. If none fit, reply 'none'."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Categories:\n{catalog_lines}\n\n"
                    f"Project description:\n{text[:1500]}\n\n"
                    "Slug:"
                ),
            }
        ],
    )
    candidate = msg.content[0].text.strip().lower() if msg.content else "none"
    if candidate in slugs:
        return Classification(candidate, 0.7, "llm: claude-haiku")
    return Classification(None, 0.0, f"llm: invalid slug '{candidate}'")


def classify(text: str, categories: CategoryIndex) -> Classification:
    """Try keyword first, fall back to LLM if confidence is too low."""
    keyword = classify_keyword(text, categories)
    if keyword.category:
        return keyword
    return classify_llm(text, categories)
