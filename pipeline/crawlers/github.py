"""GitHub repo metadata fetcher."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.budget import get_budget

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "onexus-agents-pipeline/0.1",
    }
    # Prefer user-supplied PAT (5000/hr) over Actions GITHUB_TOKEN (1000/hr).
    # Both are free; PAT requires only `public_repo` read scope.
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_repo(client: httpx.Client, full_name: str) -> dict[str, Any] | None:
    """Return canonical repo metadata or None if the repo is missing/private/forbidden.

    Treats 403 (secondary rate limit), 404 (gone/private), 410 (gone), and 451
    (legal block) as "skip this one" so a single throttled or DMCA'd repo can't
    crash a multi-thousand-repo crawl.
    """
    if not get_budget().spend("gh"):
        return None
    r = client.get(
        f"{GITHUB_API}/repos/{full_name}",
        headers=_headers(),
        timeout=15,
        follow_redirects=True,
    )
    if r.status_code in (403, 404, 410, 451):
        return None
    r.raise_for_status()
    data = r.json()

    first_commit_at = _fetch_first_commit_date(client, full_name) or data.get("created_at")

    return {
        "stars": data.get("stargazers_count"),
        "license": (data.get("license") or {}).get("spdx_id") or "Unknown",
        "homepage": data.get("homepage") or None,
        "default_branch": data.get("default_branch"),
        "last_commit_at": _parse_dt(data.get("pushed_at")),
        "first_commit_at": _parse_dt(first_commit_at),
        "description": data.get("description") or "",
        "owner_type": (data.get("owner") or {}).get("type", "User").lower(),
        "owner_html_url": (data.get("owner") or {}).get("html_url"),
        "topics": data.get("topics") or [],
        "html_url": data.get("html_url"),
        # Tier 1: already returned by /repos — capture instead of dropping.
        "forks": data.get("forks_count"),
        "watchers": data.get("subscribers_count"),
        "open_issues": data.get("open_issues_count"),
        "archived": bool(data.get("archived", False)),
        "is_fork": bool(data.get("fork", False)),
        "is_template": bool(data.get("is_template", False)),
    }


def _fetch_first_commit_date(client: httpx.Client, full_name: str) -> str | None:
    """Cheap proxy: paginate to the last commit page and grab its committer date."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/commits",
            headers=_headers(),
            params={"per_page": 1},
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return None
        link = r.headers.get("Link", "")
        last_page = 1
        for part in link.split(","):
            if 'rel="last"' in part:
                # extract page= from URL
                import re
                m = re.search(r"[?&]page=(\d+)", part)
                if m:
                    last_page = int(m.group(1))
        r2 = client.get(
            f"{GITHUB_API}/repos/{full_name}/commits",
            headers=_headers(),
            params={"per_page": 1, "page": last_page},
            timeout=15,
            follow_redirects=True,
        )
        if r2.status_code != 200 or not r2.json():
            return None
        return r2.json()[0]["commit"]["committer"]["date"]
    except Exception:
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def search_repos(client: httpx.Client, query: str, limit: int = 30) -> list[str]:
    """Search GitHub for repos matching `query`. Returns owner/name strings.

    Returns [] on 403 (secondary rate limit) or 422 (bad query) so a single
    bad query doesn't kill the whole crawl.
    """
    if not get_budget().spend("gh"):
        return []
    r = client.get(
        f"{GITHUB_API}/search/repositories",
        headers=_headers(),
        params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        timeout=20,
        follow_redirects=True,
    )
    if r.status_code in (403, 422):
        return []
    r.raise_for_status()
    return [item["full_name"] for item in r.json().get("items", [])]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _last_page_from_link(link: str) -> int:
    """Extract the last page number from a paginated API Link header.

    GitHub's REST API returns counts only via pagination — the trick is to
    request per_page=1 and read the last-page index from the Link header,
    which gives an exact count in one API call.
    """
    import re
    for part in link.split(","):
        if 'rel="last"' in part:
            m = re.search(r"[?&]page=(\d+)", part)
            if m:
                return int(m.group(1))
    return 1


def count_contributors(client: httpx.Client, full_name: str) -> int | None:
    """Total contributor count via per_page=1 pagination Link header."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/contributors",
            headers=_headers(),
            params={"per_page": 1, "anon": "false"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        link = r.headers.get("Link", "")
        if link:
            return _last_page_from_link(link)
        # No Link header → at most one page → count returned items
        body = r.json()
        return len(body) if isinstance(body, list) else None
    except Exception:
        return None


def fetch_releases_summary(client: httpx.Client, full_name: str) -> dict[str, Any] | None:
    """Total release count + most-recent release date in one call."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/releases",
            headers=_headers(),
            params={"per_page": 1},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        link = r.headers.get("Link", "")
        total = _last_page_from_link(link) if link else len(r.json() or [])
        body = r.json() or []
        latest = body[0].get("published_at") if body else None
        return {"total": total, "latest_at": _parse_dt(latest)}
    except Exception:
        return None


def count_commits_since(client: httpx.Client, full_name: str, since_iso: str) -> int | None:
    """Commits authored since `since_iso` (ISO-8601). Per-page=1 + Link pagination."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/commits",
            headers=_headers(),
            params={"per_page": 1, "since": since_iso},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        link = r.headers.get("Link", "")
        if link:
            return _last_page_from_link(link)
        body = r.json()
        return len(body) if isinstance(body, list) else 0
    except Exception:
        return None


def fetch_readme(client: httpx.Client, full_name: str) -> str | None:
    """Decoded README text or None. Uses /readme which returns base64-content."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/readme",
            headers=_headers(),
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        content = data.get("content") or ""
        encoding = data.get("encoding") or "base64"
        if encoding == "base64":
            import base64
            try:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            except Exception:
                return None
        return content
    except Exception:
        return None


def has_ci_workflows(client: httpx.Client, full_name: str, default_branch: str = "main") -> bool | None:
    """True if .github/workflows/ exists in the default branch. Single HEAD-ish GET."""
    if not get_budget().spend("gh"):
        return None
    try:
        r = client.get(
            f"{GITHUB_API}/repos/{full_name}/contents/.github/workflows",
            headers=_headers(),
            params={"ref": default_branch},
            timeout=10,
        )
        if r.status_code == 200:
            body = r.json()
            return isinstance(body, list) and len(body) > 0
        if r.status_code == 404:
            return False
        return None
    except Exception:
        return None
