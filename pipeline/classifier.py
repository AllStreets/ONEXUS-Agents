"""Category classifier — keyword heuristic with optional OpenAI fallback."""

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


LLM_MODEL = os.environ.get("ONEXUS_CLASSIFIER_MODEL", "gpt-5.4-mini")


def classify_llm(text: str, categories: CategoryIndex) -> Classification:
    """Fallback: ask an OpenAI model to pick a category. Cheap + bounded output."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return Classification(None, 0.0, "llm: no OPENAI_API_KEY set")
    try:
        from openai import OpenAI
    except ImportError:
        return Classification(None, 0.0, "llm: openai not installed")

    slugs = [c.slug for c in categories.categories]
    catalog_lines = "\n".join(f"- {c.slug}: {c.description}" for c in categories.categories)

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        max_completion_tokens=64,
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify open-source AI agents into a single category slug. "
                    "Reply with ONLY the slug, nothing else. If none fit, reply 'none'."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Categories:\n{catalog_lines}\n\n"
                    f"Project description:\n{text[:1500]}\n\n"
                    "Slug:"
                ),
            },
        ],
    )
    candidate = (completion.choices[0].message.content or "none").strip().lower()
    if candidate in slugs:
        return Classification(candidate, 0.7, f"llm: {LLM_MODEL}")
    return Classification(None, 0.0, f"llm: invalid slug '{candidate}'")


def classify(text: str, categories: CategoryIndex) -> Classification:
    """Try keyword first, fall back to LLM if confidence is too low."""
    keyword = classify_keyword(text, categories)
    if keyword.category:
        return keyword
    return classify_llm(text, categories)
