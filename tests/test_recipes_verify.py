"""The verifier builds a recipe from a fixed template, starts it confined and asks for its
tools. The integration tests build real published servers and need Docker and network;
they run when ONEXUS_RECIPES_DOCKER=1."""
from __future__ import annotations

import os
import shutil

import pytest

from pipeline.recipes import verify as v
from pipeline.recipes.schema import EnvVar, Install, Recipe, RecipeSource


def recipe(kind="npm", **install):
    return Recipe(slug="t", source=RecipeSource(repo="o/t", commit="c"), derived_from="readme-config",
                  install=Install(kind=kind, **install), command=["srv"], args=["--stdio"],
                  env=[EnvVar(name="GITHUB_TOKEN", required=True, secret=True)])


def test_templates_pin_their_base_and_drop_root():
    npm = v.dockerfile(recipe(package="@acme/x", version="1.2.3"))
    assert v.NODE_BASE in npm and "npm install -g" in npm and "@acme/x@1.2.3" in npm
    assert npm.strip().endswith("USER 65534:65534")
    py = v.dockerfile(recipe("pypi", package="x-mcp[cli]", version="0.4.0"))
    assert v.PYTHON_BASE in py and "x-mcp[cli]==0.4.0" in py and "USER 65534:65534" in py
    assert v.dockerfile(recipe("oci", image="ghcr.io/a/b:1")) is None
    assert "@sha256:" in v.NODE_BASE and "@sha256:" in v.PYTHON_BASE
    assert "OPENSSL_armcap=0x1fff" in npm and "OPENSSL_armcap=0x1fff" in py


def test_run_argv_uses_onexus_confinement():
    argv = v.run_argv("img", recipe(package="x", version="1"), {"GITHUB_TOKEN": v.PLACEHOLDER})
    joined = " ".join(argv)
    for flag in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges",
                 "--user 65534:65534", "/work:rw,size=256m,uid=65534,gid=65534"):
        assert flag in joined
    assert argv[-3:] == ["img", "srv", "--stdio"]
    assert f"GITHUB_TOKEN={v.PLACEHOLDER}" in argv


@pytest.mark.parametrize("host", ["json-schema.org", "www.w3.org", "github.com", "registry.npmjs.org",
                                  "localhost", "api.example.com", "modelcontextprotocol.io",
                                  "raw.githubusercontent.com", "svc.internal"])
def test_documentation_and_example_hosts_are_not_proposed(host):
    assert v.not_a_service(host)


@pytest.mark.parametrize("host", ["api.github.com", "api.firecrawl.dev", "slack.com", "api.notion.com"])
def test_service_hosts_are_kept(host):
    assert not v.not_a_service(host)


def test_api_github_com_is_a_service_even_though_github_com_is_not():
    assert v.not_a_service("github.com") and not v.not_a_service("api.github.com")


docker = pytest.mark.skipif(
    os.environ.get("ONEXUS_RECIPES_DOCKER") != "1" or not shutil.which("docker"),
    reason="set ONEXUS_RECIPES_DOCKER=1 (needs Docker and network)")


@docker
def test_verifies_a_real_npm_server():
    r = Recipe(slug="everything", source=RecipeSource(repo="modelcontextprotocol/servers", commit="x"),
               derived_from="readme-config",
               install=Install(kind="npm", package="@modelcontextprotocol/server-everything", version="2.0.0"),
               command=["mcp-server-everything"])
    out = v.verify(r)
    assert out.verified.ok, out.verified.reason
    assert "echo" in out.verified.tools
    assert out.dockerfile and v.NODE_BASE in out.dockerfile


@docker
def test_verifies_a_real_pypi_server():
    r = Recipe(slug="fetch", source=RecipeSource(repo="modelcontextprotocol/servers", commit="x"),
               derived_from="readme-config",
               install=Install(kind="pypi", package="mcp-server-fetch", version="2026.10.19"),
               command=["mcp-server-fetch"])
    out = v.verify(r)
    assert out.verified.ok, out.verified.reason
    assert out.verified.tools == ["fetch"]


@docker
def test_a_server_that_exits_is_reported_with_its_stage():
    r = Recipe(slug="bad", source=RecipeSource(repo="o/bad", commit="x"), derived_from="readme-config",
               install=Install(kind="pypi", package="mcp-server-fetch", version="2026.10.19"),
               command=["python", "-c", "import sys; sys.exit(3)"])
    out = v.verify(r)
    assert not out.verified.ok and out.verified.stage == "start"
    assert "code 3" in out.verified.reason


def test_native_templates_build_with_compilers_and_run_slim():
    npm = v.dockerfile(recipe(package="gitnexus", version="1.6.12"), native=True)
    assert npm.startswith(f"FROM {v.NODE_BUILD} AS build") and f"FROM {v.NODE_BASE}" in npm
    assert "COPY --from=build /usr/local/lib/node_modules" in npm and npm.strip().endswith("USER 65534:65534")
    py = v.dockerfile(recipe("pypi", package="lxml-mcp", version="1.0"), native=True)
    assert "pip wheel" in py and "--no-index --find-links /wheels" in py and f"FROM {v.PYTHON_BASE}" in py


@pytest.mark.parametrize("log,needs", [
    ("npm error gyp ERR! find Python", True),
    ("Failed building wheel for lxml", True),
    ("error: command 'gcc' failed: No such file or directory", True),
    ("npm error 404 Not Found - GET https://registry.npmjs.org/x", False),
    ("ERROR: No matching distribution found for x==1", False),
])
def test_compiler_fallback_triggers_only_on_compiler_errors(log, needs):
    assert bool(v._NEEDS_COMPILER.search(log)) is needs
