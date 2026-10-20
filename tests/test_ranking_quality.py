"""The ranking keeps lists, courses and guides out of the top of a category."""

from datetime import UTC, datetime, timedelta

import httpx

import pipeline.nightly as nightly
from pipeline.crawlers import github as gh
from pipeline.ranking import not_an_agent, rank_category
from pipeline.schema import Agent, Category


def _agent(slug: str, tagline: str = "An agent that does real work.", stars: int = 1000) -> Agent:
    now = datetime.now(UTC)
    return Agent.model_validate(
        {
            "slug": slug,
            "name": slug,
            "tagline": tagline,
            "category": "coding",
            "author": {"type": "user", "handle": "someone", "url": "https://github.com/someone"},
            "source": {"primary": "github", "github": f"someone/{slug}"},
            "license": "MIT",
            "metrics": {
                "stars": stars,
                "forks": stars // 10,
                "last_commit_at": (now - timedelta(days=3)).isoformat(),
                "first_commit_at": (now - timedelta(days=400)).isoformat(),
            },
            "discovered_via": "auto",
            "first_seen_at": now.isoformat(),
            "last_refreshed_at": now.isoformat(),
        }
    )


def _category() -> Category:
    return Category.model_validate(
        {
            "slug": "coding",
            "name": "Coding",
            "description": "Coding agents",
            "seed_keywords": ["coding agent"],
            "github_search_queries": ["topic:coding-agent"],
        }
    )


def test_lists_courses_and_guides_are_recognised():
    assert not_an_agent(_agent("awesome-python"))
    assert not_an_agent(_agent("ai-agent-papers"))
    assert not_an_agent(_agent("howtocook", "Programmer's guide about how to cook at home."))
    assert not_an_agent(_agent("llm-course", "A course on building agents"))
    assert not_an_agent(_agent("agents-x", "A curated list of agent frameworks"))


def test_real_tools_are_not_caught():
    assert not_an_agent(_agent("aider", "AI pair programming in your terminal")) is None
    assert not_an_agent(_agent("vanilla-cookbook", "A deceptively simple recipe manager.")) is None
    assert not_an_agent(_agent("open-interpreter", "A natural language interface for computers")) is None


def test_a_popular_list_ranks_below_a_modest_agent():
    ranked = rank_category([_agent("awesome-agents", stars=90_000), _agent("small-agent", stars=200)], _category())
    assert [a.slug for a in ranked] == ["small-agent", "awesome-agents"]
    assert ranked[1].composite_score == 0.0


def test_a_run_where_most_seeds_fail_is_systemic(monkeypatch):
    monkeypatch.setattr(nightly, "SEED_HEALTH", {"ok": 3, "failed": 17})
    assert nightly.systemic_failure()
    monkeypatch.setattr(nightly, "SEED_HEALTH", {"ok": 18, "failed": 2})
    assert not nightly.systemic_failure()
    monkeypatch.setattr(nightly, "SEED_HEALTH", {"ok": 0, "failed": 3})
    assert not nightly.systemic_failure(), "too few seeds to judge"


def test_a_rejected_pat_falls_back_to_the_actions_token(monkeypatch):
    monkeypatch.setenv("GH_PAT", "expired-pat")
    monkeypatch.setenv("GITHUB_TOKEN", "actions-token")
    monkeypatch.setattr(gh, "_PAT_REJECTED", False)
    assert gh._headers()["Authorization"] == "Bearer expired-pat"
    request = httpx.Request("GET", "https://api.github.com/repos/a/b", headers=gh._headers())
    gh.auth_fallback_hook(httpx.Response(401, request=request))
    assert gh._headers()["Authorization"] == "Bearer actions-token"


def test_readme_counts_render_from_the_catalog():
    from pipeline.readme_counts import render

    text = (
        "badge/indexed-5%2C858_repos- badge/self--declare_MCP-690-\n"
        "<!-- counts:start -->old<!-- counts:end -->"
    )
    out = render(text, {"indexed": 1234, "mcp": 56, "benchmarked": 7, "adapters": 21}, "2026-10-20")
    assert "badge/indexed-1%2C234_repos-" in out
    assert "badge/self--declare_MCP-56-" in out
    assert "  1,234   repos indexed" in out
    assert "7 entries currently carry a benchmark score" in out
    assert "old" not in out
