"""Fetch what the resolver reads: files from an agent's repository at one exact commit,
and package metadata from npm and PyPI."""
from __future__ import annotations

import base64
from urllib.parse import quote

import httpx

from pipeline.crawlers import github as gh
from pipeline.recipes.resolve import Evidence, Published, repo_of

GITHUB_API = "https://api.github.com"
FILES = {"server_json": "server.json", "package_json": "package.json", "pyproject": "pyproject.toml"}


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response | None:
    try:
        r = client.get(url, timeout=20, **kw)
    except httpx.HTTPError:
        return None
    return r if r.status_code == 200 else None


def head_commit(client: httpx.Client, repo: str) -> str | None:
    r = _get(client, f"{GITHUB_API}/repos/{repo}/commits/HEAD", headers=gh._headers())
    return r.json().get("sha") if r else None


def repo_file(client: httpx.Client, repo: str, path: str, ref: str) -> str | None:
    r = _get(client, f"{GITHUB_API}/repos/{repo}/contents/{path}", params={"ref": ref}, headers=gh._headers())
    if not r:
        return None
    data = r.json()
    if not isinstance(data, dict) or data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data.get("content") or "").decode("utf-8", errors="replace")
    except ValueError:
        return None


def readme_at(client: httpx.Client, repo: str, ref: str) -> str | None:
    r = _get(client, f"{GITHUB_API}/repos/{repo}/readme", params={"ref": ref}, headers=gh._headers())
    if not r:
        return None
    try:
        return base64.b64decode(r.json().get("content") or "").decode("utf-8", errors="replace")
    except ValueError:
        return None


def evidence(client: httpx.Client, slug: str, repo: str, license: str) -> Evidence | None:
    commit = head_commit(client, repo)
    if not commit:
        return None
    ev = Evidence(slug=slug, repo=repo, commit=commit, license=license)
    for attr, path in FILES.items():
        setattr(ev, attr, repo_file(client, repo, path, commit))
    ev.readme = readme_at(client, repo, commit)
    return ev


class LiveRegistry:
    """npm and PyPI, asked once per package and version per run."""

    def __init__(self, client: httpx.Client):
        self._c = client
        self._cache: dict = {}

    def npm(self, package: str, version: str | None = None) -> Published | None:
        key = ("npm", package, version)
        if key not in self._cache:
            name = quote(package, safe="@")
            r = _get(self._c, f"https://registry.npmjs.org/{name}/{version or 'latest'}")
            out = None
            if r:
                d = r.json()
                bins = d.get("bin") or {}
                if isinstance(bins, str):
                    bins = {package.split("/")[-1]: bins}
                repo = d.get("repository")
                url = repo.get("url", "") if isinstance(repo, dict) else (repo or "")
                if url and "/" in url and ":" not in url and "github" not in url:
                    url = f"github.com/{url}"  # npm shorthand "owner/name"
                repos = {r for r in [repo_of(url), repo_of(d.get("homepage") or "")] if r}
                if d.get("version"):
                    out = Published(version=d["version"], bins=dict(bins), repos=repos)
            self._cache[key] = out
        return self._cache[key]

    def pypi(self, package: str, version: str | None = None) -> Published | None:
        key = ("pypi", package, version)
        if key not in self._cache:
            url = f"https://pypi.org/pypi/{package}/{version}/json" if version else f"https://pypi.org/pypi/{package}/json"
            r = _get(self._c, url)
            info = r.json().get("info", {}) if r else {}
            v = info.get("version")
            urls = list((info.get("project_urls") or {}).values()) + [info.get("home_page") or ""]
            repos = {x for x in (repo_of(u) for u in urls) if x}
            self._cache[key] = Published(version=v, repos=repos) if v else None
        return self._cache[key]
