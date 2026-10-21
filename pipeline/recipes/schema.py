"""The recipe: how to install one catalog agent as a confined MCP server.

A recipe is written by the resolver from evidence in the agent's repository and package
registry, and completed by the verifier, which builds it, starts it with ONEXUS's
confinement flags and records what it served. ONEXUS installs only verified recipes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RECIPE_VERSION = 1


class RecipeSource(BaseModel):
    repo: str
    commit: str


class Install(BaseModel):
    kind: Literal["npm", "pypi", "oci"]
    # npm and pypi: the package and its exact version. oci: the image, and its digest once verified.
    package: str | None = None
    version: str | None = None
    image: str | None = None
    digest: str | None = None


class EnvVar(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    required: bool = False
    secret: bool = False
    description: str = ""


class Hosts(BaseModel):
    proposed: list[str] = Field(default_factory=list)
    # host -> where it was found, e.g. "dist/index.js:12" or "env GITHUB_TOKEN"
    evidence: dict[str, list[str]] = Field(default_factory=dict)


class Verified(BaseModel):
    at: datetime
    ok: bool
    stage: Literal["build", "start", "handshake", "done"] = "done"
    reason: str = ""
    tools: list[str] = Field(default_factory=list)
    handshake_ms: int | None = None
    server_name: str = ""
    server_version: str = ""


class Prebuilt(BaseModel):
    image: str


class Recipe(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    recipe_version: int = RECIPE_VERSION
    source: RecipeSource
    derived_from: Literal["server.json", "readme-config", "package-manifest"]
    install: Install
    # argv inside the container; for oci an empty command means the image's own entrypoint,
    # and `args` are passed to it.
    command: list[str] = Field(default_factory=list)
    args: list[str] = Field(default_factory=list)
    transport: Literal["stdio"] = "stdio"
    env: list[EnvVar] = Field(default_factory=list)
    hosts: Hosts = Field(default_factory=Hosts)
    license: str = "Unknown"
    dockerfile: str | None = None
    verified: Verified | None = None
    prebuilt: Prebuilt | None = None

    @property
    def installable(self) -> bool:
        return bool(self.verified and self.verified.ok)
