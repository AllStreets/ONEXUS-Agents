"""Category classifier — keyword heuristic with LLM fallback chain.

Fallback chain when keyword match doesn't clear the threshold:
  1. Anthropic Claude Haiku  (if ANTHROPIC_API_KEY set)
  2. OpenAI gpt-4o-mini      (if OPENAI_API_KEY set)
  3. give up

Each provider call is bounded to a few tokens of output (the slug only),
so a missed classification costs fractions of a cent. The chain stops at
the first provider that returns a valid slug.
"""

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


def _prompt_parts(text: str, categories: CategoryIndex) -> tuple[str, str, list[str]]:
    system = (
        "You classify open-source AI agents into a single category slug. "
        "Reply with ONLY the slug, nothing else. If none fit, reply 'none'."
    )
    catalog_lines = "\n".join(f"- {c.slug}: {c.description}" for c in categories.categories)
    user = (
        f"Categories:\n{catalog_lines}\n\n"
        f"Project description:\n{text[:1500]}\n\n"
        "Slug:"
    )
    return system, user, [c.slug for c in categories.categories]


def classify_anthropic(text: str, categories: CategoryIndex) -> Classification:
    """Ask Claude Haiku to pick a category. Cheap + bounded output."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return Classification(None, 0.0, "anthropic: no ANTHROPIC_API_KEY set")
    try:
        from anthropic import Anthropic
    except ImportError:
        return Classification(None, 0.0, "anthropic: SDK not installed")

    system, user, slugs = _prompt_parts(text, categories)
    try:
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        candidate = msg.content[0].text.strip().lower() if msg.content else "none"
    except Exception as e:  # noqa: BLE001
        return Classification(None, 0.0, f"anthropic: {type(e).__name__}: {e}")

    if candidate in slugs:
        return Classification(candidate, 0.7, "anthropic: claude-haiku")
    return Classification(None, 0.0, f"anthropic: invalid slug '{candidate}'")


def classify_openai(text: str, categories: CategoryIndex) -> Classification:
    """Ask OpenAI gpt-4o-mini to pick a category. Fallback after Anthropic."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return Classification(None, 0.0, "openai: no OPENAI_API_KEY set")
    try:
        from openai import OpenAI
    except ImportError:
        return Classification(None, 0.0, "openai: SDK not installed")

    system, user, slugs = _prompt_parts(text, categories)
    try:
        client = OpenAI(api_key=api_key)
        msg = client.chat.completions.create(
            model="gpt-5.4-mini",
            max_tokens=64,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        candidate = (msg.choices[0].message.content or "none").strip().lower()
    except Exception as e:  # noqa: BLE001
        return Classification(None, 0.0, f"openai: {type(e).__name__}: {e}")

    if candidate in slugs:
        return Classification(candidate, 0.65, "openai: gpt-5.4-mini")
    return Classification(None, 0.0, f"openai: invalid slug '{candidate}'")


# Kept for back-compat with existing imports / external callers.
classify_llm = classify_anthropic


def classify(text: str, categories: CategoryIndex) -> Classification:
    """Try keyword first, fall back to OpenAI gpt-5.4-mini.

    Anthropic is intentionally NOT in the default chain — operator choice.
    classify_anthropic() remains importable for callers that want it.
    """
    keyword = classify_keyword(text, categories)
    if keyword.category:
        return keyword
    return classify_openai(text, categories)


def classify_with_hint(
    text: str, categories: CategoryIndex, hint_slug: str
) -> Classification:
    """Validate or correct a query-origin category hint, calling LLM only when needed.

    Discovery-time use case: a broadened search query from category X surfaced
    a repo. We want to confirm X is right (cheap) or override to the actual
    category (LLM only as last resort).

      keyword agrees with hint → return hint (free)
      keyword strongly disagrees (confidence ≥ 0.5) → trust keyword (free)
      keyword is ambiguous → ask gpt-5.4-mini
    """
    keyword = classify_keyword(text, categories)
    if keyword.category == hint_slug:
        return keyword
    if keyword.category and keyword.confidence >= 0.5:
        return keyword
    return classify_openai(text, categories)
