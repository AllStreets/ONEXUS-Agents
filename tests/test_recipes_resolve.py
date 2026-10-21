"""The resolver turns repository evidence into a recipe, or says why it can't."""
from __future__ import annotations

import json

from pipeline.recipes.resolve import Evidence, NoRecipe, Published, mcp_server_blocks, resolve
from pipeline.recipes.schema import Recipe


class FakeRegistry:
    def __init__(self, npm=None, pypi=None):
        self._npm, self._pypi = npm or {}, pypi or {}

    def npm(self, package, version=None):
        p = self._npm.get(package)
        if not p:
            return None
        return Published(version=version or p[0], bins=p[1], repos=set(p[2]) if len(p) > 2 else {"o/x"})

    def pypi(self, package, version=None):
        v = self._pypi.get(package)
        if not v:
            return None
        ver, repos = (v, {"o/x"}) if isinstance(v, str) else v
        return Published(version=version or ver, repos=set(repos))


REG = FakeRegistry(
    npm={
        "@acme/github-mcp": ("2.1.0", {"github-mcp": "dist/index.js"}),
        "weather-mcp": ("0.3.1", {"weather-mcp": "build/index.js"}),
        "multi-bin": ("1.0.0", {"a": "a.js", "b": "b.js"}),
    },
    pypi={"mcp-server-fetch": "2025.4.7", "notes-mcp": "1.2.0"},
)


def ev(**kw):
    return Evidence(slug="x", repo="o/x", commit="abc123", license="MIT", **kw)


def readme(block: dict) -> str:
    return "# X\n\nAdd this to your config:\n\n```json\n" + json.dumps({"mcpServers": block}, indent=2) + "\n```\n"


def test_server_json_npm_with_env():
    sj = json.dumps({
        "name": "io.github.acme/github",
        "packages": [{
            "registryType": "npm", "identifier": "@acme/github-mcp", "version": "2.1.0",
            "transport": {"type": "stdio"},
            "environmentVariables": [{"name": "GITHUB_TOKEN", "isRequired": True, "isSecret": True}],
        }],
    })
    r = resolve(ev(server_json=sj), REG)
    assert isinstance(r, Recipe)
    assert r.derived_from == "server.json"
    assert (r.install.kind, r.install.package, r.install.version) == ("npm", "@acme/github-mcp", "2.1.0")
    assert r.command == ["github-mcp"]
    assert [(e.name, e.required, e.secret) for e in r.env] == [("GITHUB_TOKEN", True, True)]
    assert r.source.commit == "abc123" and r.license == "MIT" and r.verified is None


def test_server_json_legacy_snake_case_pypi():
    sj = json.dumps({"packages": [{"registry_name": "pypi", "name": "mcp-server-fetch", "version": "2025.4.7"}]})
    r = resolve(ev(server_json=sj), REG)
    assert isinstance(r, Recipe)
    assert (r.install.kind, r.install.package, r.command) == ("pypi", "mcp-server-fetch", ["mcp-server-fetch"])


def test_server_json_oci_image():
    sj = json.dumps({"packages": [{"registryType": "oci", "identifier": "ghcr.io/acme/tool", "version": "1.4",
                                   "transport": {"type": "stdio"}}]})
    r = resolve(ev(server_json=sj), REG)
    assert isinstance(r, Recipe) and r.install.kind == "oci" and r.install.image == "ghcr.io/acme/tool:1.4"
    assert r.command == []


def test_server_json_remote_only_has_no_recipe():
    r = resolve(ev(server_json=json.dumps({"remotes": [{"type": "streamable-http", "url": "https://x"}]})), REG)
    assert isinstance(r, NoRecipe) and "remote" in r.reason


def test_server_json_required_argument_without_value():
    sj = json.dumps({"packages": [{"registryType": "npm", "identifier": "weather-mcp",
                                   "packageArguments": [{"type": "positional", "valueHint": "directory", "isRequired": True}]}]})
    r = resolve(ev(server_json=sj), REG)
    assert isinstance(r, NoRecipe) and "only you can fill in" in r.reason


def test_readme_npx_block():
    r = resolve(ev(readme=readme({"weather": {"command": "npx", "args": ["-y", "weather-mcp"],
                                              "env": {"WEATHER_API_KEY": "your-key"}}})), REG)
    assert isinstance(r, Recipe) and r.derived_from == "readme-config"
    assert (r.install.package, r.install.version, r.command) == ("weather-mcp", "0.3.1", ["weather-mcp"])
    assert r.env[0].name == "WEATHER_API_KEY" and r.env[0].secret


def test_readme_pinned_npx_version_is_kept():
    r = resolve(ev(readme=readme({"w": {"command": "npx", "args": ["-y", "weather-mcp@0.2.0"]}})), REG)
    assert isinstance(r, Recipe) and r.install.version == "0.2.0"


def test_readme_uvx_block_and_from_form():
    r = resolve(ev(readme=readme({"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}})), REG)
    assert isinstance(r, Recipe) and (r.install.kind, r.command) == ("pypi", ["mcp-server-fetch"])
    r = resolve(ev(readme=readme({"n": {"command": "uvx", "args": ["--from", "notes-mcp", "notes-server"]}})), REG)
    assert isinstance(r, Recipe) and (r.install.package, r.command) == ("notes-mcp", ["notes-server"])


def test_readme_docker_run_block():
    r = resolve(ev(readme=readme({"t": {"command": "docker", "args": [
        "run", "-i", "--rm", "-e", "API_TOKEN", "ghcr.io/o/tool:1.4", "--read-only"]}})), REG)
    assert isinstance(r, Recipe) and r.install.image == "ghcr.io/o/tool:1.4"
    assert r.args == ["--read-only"] and r.env[0].name == "API_TOKEN"


def test_readme_docker_mount_is_refused():
    r = resolve(ev(readme=readme({"t": {"command": "docker", "args": ["run", "-i", "-v", "/data:/data", "acme/tool"]}})), REG)
    assert isinstance(r, NoRecipe) and "mounts" in r.reason


def test_readme_placeholder_path_is_refused():
    r = resolve(ev(readme=readme({"fs": {"command": "npx", "args": ["-y", "weather-mcp", "/Users/you/Documents"]}})), REG)
    assert isinstance(r, NoRecipe) and "only you can fill in" in r.reason


def test_readme_local_clone_is_refused():
    r = resolve(ev(readme=readme({"x": {"command": "node", "args": ["/path/to/build/index.js"]}})), REG)
    assert isinstance(r, NoRecipe) and "local copy" in r.reason


def test_readme_unpublished_package_is_refused():
    r = resolve(ev(readme=readme({"x": {"command": "npx", "args": ["-y", "not-on-npm"]}})), REG)
    assert isinstance(r, NoRecipe) and "not published" in r.reason


def test_readme_skips_a_bad_entry_and_takes_the_next_good_one():
    r = resolve(ev(readme=readme({
        "local": {"command": "node", "args": ["index.js"]},
        "pub": {"command": "npx", "args": ["-y", "weather-mcp"]},
    })), REG)
    assert isinstance(r, Recipe) and r.install.package == "weather-mcp"


def test_readme_with_comments_and_trailing_commas():
    text = '```jsonc\n{\n  "mcpServers": {\n    // the server\n    "w": {"command": "npx", "args": ["-y", "weather-mcp",],},\n  }\n}\n```'
    assert mcp_server_blocks(text)[0]["args"] == ["-y", "weather-mcp"]


def test_ambiguous_npm_bins_are_refused():
    r = resolve(ev(readme=readme({"m": {"command": "npx", "args": ["-y", "multi-bin"]}})), REG)
    assert isinstance(r, NoRecipe) and "several commands" in r.reason


def test_package_json_mcp_server():
    pj = json.dumps({"name": "weather-mcp", "bin": {"weather-mcp": "build/index.js"},
                     "dependencies": {"@modelcontextprotocol/sdk": "^1.0.0"}})
    r = resolve(ev(package_json=pj), REG)
    assert isinstance(r, Recipe) and r.derived_from == "package-manifest" and r.command == ["weather-mcp"]


def test_pyproject_mcp_server():
    pp = '[project]\nname = "notes-mcp"\ndependencies = ["mcp[cli]>=1.2", "httpx"]\n[project.scripts]\nnotes-mcp = "notes.server:main"\n'
    r = resolve(ev(pyproject=pp), REG)
    assert isinstance(r, Recipe) and (r.install.kind, r.command) == ("pypi", ["notes-mcp"])


def test_an_mcp_client_app_has_no_recipe():
    # An app that USES MCP servers: mentions MCP, ships no server and no published package.
    pj = json.dumps({"name": "chat-ui", "private": True, "dependencies": {"react": "^19"}})
    r = resolve(ev(readme="# Chat UI\n\nConnect your MCP servers in Settings.", package_json=pj), REG)
    assert isinstance(r, NoRecipe)


def test_an_awesome_list_has_no_recipe():
    r = resolve(ev(readme="# Awesome MCP agents\n\n- [a](https://x) an MCP server\n- [b](https://y)"), REG)
    assert isinstance(r, NoRecipe)


def test_server_json_wins_over_readme():
    sj = json.dumps({"packages": [{"registryType": "pypi", "identifier": "notes-mcp", "version": "1.2.0"}]})
    r = resolve(ev(server_json=sj, readme=readme({"w": {"command": "npx", "args": ["-y", "weather-mcp"]}})), REG)
    assert isinstance(r, Recipe) and r.derived_from == "server.json" and r.install.package == "notes-mcp"


def test_pypi_extras_are_kept_in_the_install_spec():
    reg = FakeRegistry(pypi={"browser-harness": "0.4.0"})
    r = resolve(ev(readme=readme({"b": {"command": "uvx", "args": ["browser-harness[mcp]"]}})), reg)
    assert isinstance(r, Recipe)
    assert (r.install.package, r.install.version, r.command) == ("browser-harness[mcp]", "0.4.0", ["browser-harness"])


def test_a_readme_naming_someone_elses_package_is_refused():
    reg = FakeRegistry(npm={"other-mcp": ("1.0.0", {"other-mcp": "i.js"}, ["someone/else"])})
    r = resolve(ev(readme=readme({"o": {"command": "npx", "args": ["-y", "other-mcp"]}})), reg)
    assert isinstance(r, NoRecipe) and "someone/else, not this repository" in r.reason


def test_a_package_that_names_no_repository_is_refused_from_a_readme():
    reg = FakeRegistry(npm={"anon-mcp": ("1.0.0", {"anon-mcp": "i.js"}, [])})
    r = resolve(ev(readme=readme({"a": {"command": "npx", "args": ["-y", "anon-mcp"]}})), reg)
    assert isinstance(r, NoRecipe) and "doesn't say which repository" in r.reason


def test_server_json_is_trusted_as_the_repositorys_own_claim():
    reg = FakeRegistry(npm={"@heyclaude/mcp": ("0.4.0", {"heyclaude-mcp": "i.js"}, [])})
    sj = json.dumps({"packages": [{"registryType": "npm", "identifier": "@heyclaude/mcp", "version": "0.4.0"}]})
    assert isinstance(resolve(ev(server_json=sj), reg), Recipe)


def test_a_docker_image_from_another_namespace_is_refused():
    r = resolve(ev(readme=readme({"t": {"command": "docker", "args": ["run", "-i", "mcp/github"]}})), REG)
    assert isinstance(r, NoRecipe) and "isn't published under o" in r.reason


def test_repo_of_normalizes_registry_urls():
    from pipeline.recipes.resolve import repo_of
    assert repo_of("git+https://github.com/Owner/Name.git") == "owner/name"
    assert repo_of("git@github.com:owner/name.git") == "owner/name"
    assert repo_of("https://github.com/owner/name/tree/main/src/x") == "owner/name"
    assert repo_of("https://gitlab.com/a/b") is None


def test_a_package_from_another_repo_of_the_same_owner_is_accepted():
    reg = FakeRegistry(npm={"x-mcp": ("1.0.0", {"x-mcp": "i.js"}, ["o/x-mcp-server"])})
    r = resolve(ev(readme=readme({"x": {"command": "npx", "args": ["-y", "x-mcp"]}})), reg)
    assert isinstance(r, Recipe) and r.install.package == "x-mcp"
