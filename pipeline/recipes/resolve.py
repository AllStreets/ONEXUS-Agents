"""Turn evidence from an agent's repository into a recipe, or a reason there isn't one.

Pure functions: the caller fetches the evidence (pipeline/recipes/fetch.py) and passes a
registry that answers "is this package published, and as what". Sources are tried in
order of exactness and the first that yields a recipe wins:

  1. server.json, the official MCP Registry format
  2. the README's "mcpServers" config block
  3. the package manifest (package.json or pyproject.toml) of a published MCP server

Nothing here guesses. When the evidence is ambiguous (two commands, an argument that is
a placeholder for the reader's own path), the answer is no recipe, with the reason.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from typing import Protocol

from pipeline.recipes.schema import EnvVar, Install, Recipe, RecipeSource


@dataclass
class Evidence:
    slug: str
    repo: str
    commit: str
    license: str = "Unknown"
    server_json: str | None = None
    readme: str | None = None
    package_json: str | None = None
    pyproject: str | None = None


@dataclass
class Published:
    version: str
    # npm: the package's bin commands (name -> path); pypi: unknown until installed
    bins: dict[str, str] = field(default_factory=dict)
    # repositories the registry says the package comes from, as "owner/name", lowercase
    repos: set[str] = field(default_factory=set)


def repo_of(url: str) -> str | None:
    """'git+https://github.com/Owner/Name.git' -> 'owner/name' (GitHub only)."""
    m = re.search(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$", url or "")
    return f"{m.group(1)}/{m.group(2)}".lower() if m else None


def _owns(ev: Evidence, derived_from: str, what: str, pub: Published) -> NoRecipe | None:
    """A README or manifest can name someone else's package; only accept one whose registry
    entry says it comes from this repository. server.json is the repository's own claim."""
    if derived_from == "server.json":
        return None
    if ev.repo.lower() in pub.repos:
        return None
    owner = ev.repo.split("/")[0].lower()
    if any(r.split("/")[0] == owner for r in pub.repos):
        return None  # another repository of the same owner, like firecrawl/firecrawl-mcp-server
    if pub.repos:
        return NoRecipe(f"{what} comes from {', '.join(sorted(pub.repos))}, not this repository")
    return NoRecipe(f"{what} doesn't say which repository it comes from, so it can't be tied to this one")


class Registry(Protocol):
    def npm(self, package: str, version: str | None = None) -> Published | None: ...
    def pypi(self, package: str, version: str | None = None) -> Published | None: ...


@dataclass
class NoRecipe:
    reason: str


# Arguments that stand for something only the reader knows: their own paths, keys, ids.
_PLACEHOLDER = re.compile(
    r"(/path/to|/Users/|/home/|C:\\|<[^>]+>|\{[^}]+\}|\$\{|YOUR[_-]|your[-_]|xxx|\.\.\.)", re.I
)
_NPM_NAME = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")
_PYPI_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?(@sha256:[a-f0-9]{64})?$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def resolve(ev: Evidence, registry: Registry) -> Recipe | NoRecipe:
    reasons = []
    for source in (_from_server_json, _from_readme, _from_manifest):
        out = source(ev, registry)
        if isinstance(out, Recipe):
            return out
        if out is not None:
            reasons.append(out.reason)
    return NoRecipe("; ".join(reasons) or "no server.json, no mcpServers block, no published MCP package")


def _recipe(ev: Evidence, derived_from: str, install: Install, command: list[str],
            args: list[str], env: list[EnvVar]) -> Recipe:
    return Recipe(
        slug=ev.slug, source=RecipeSource(repo=ev.repo, commit=ev.commit),
        derived_from=derived_from, install=install, command=command, args=args,
        env=_dedupe_env(env), license=ev.license,
    )


def _dedupe_env(env: list[EnvVar]) -> list[EnvVar]:
    seen: dict[str, EnvVar] = {}
    for e in env:
        if e.name in seen:
            prev = seen[e.name]
            seen[e.name] = EnvVar(name=e.name, required=prev.required or e.required,
                                  secret=prev.secret or e.secret,
                                  description=prev.description or e.description)
        else:
            seen[e.name] = e
    return list(seen.values())


def _placeholder(args: list[str]) -> str | None:
    for a in args:
        if _PLACEHOLDER.search(a):
            return a
    return None


# --- npm / pypi / oci from a launch line ------------------------------------------------


def _split_npm_spec(spec: str) -> tuple[str, str | None]:
    """'@scope/pkg@1.2.3' -> ('@scope/pkg', '1.2.3'); 'pkg' -> ('pkg', None)."""
    if spec.startswith("@"):
        name, _, ver = spec[1:].partition("@")
        return "@" + name, ver or None
    name, _, ver = spec.partition("@")
    return name, ver or None


def _npm_bin(package: str, pub: Published) -> str | NoRecipe:
    bins = pub.bins
    if not bins:
        return NoRecipe(f"npm package {package} declares no command")
    if len(bins) == 1:
        return next(iter(bins))
    base = package.split("/")[-1]
    if base in bins:
        return base
    mcp = [b for b in bins if "mcp" in b.lower()]
    if len(mcp) == 1:
        return mcp[0]
    return NoRecipe(f"npm package {package} has several commands ({', '.join(sorted(bins))})")


def _npm(ev, registry, derived_from, spec, rest, env) -> Recipe | NoRecipe:
    package, version = _split_npm_spec(spec)
    if not _NPM_NAME.match(package):
        return NoRecipe(f"not an npm package name: {spec!r}")
    if bad := _placeholder(rest):
        return NoRecipe(f"needs an argument only you can fill in: {bad!r}")
    pub = registry.npm(package, version)
    if not pub:
        return NoRecipe(f"npm package {package} is not published")
    if foreign := _owns(ev, derived_from, f"npm package {package}", pub):
        return foreign
    command = _npm_bin(package, pub)
    if isinstance(command, NoRecipe):
        return command
    return _recipe(ev, derived_from, Install(kind="npm", package=package, version=pub.version),
                   [command], rest, env)


def _pypi(ev, registry, derived_from, package, command, rest, env) -> Recipe | NoRecipe:
    spec, _, version = package.partition("==")
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[A-Za-z0-9._,-]+\])?$", spec)
    if not m:
        return NoRecipe(f"not a PyPI package name: {package!r}")
    base = m.group(1)
    if bad := _placeholder(rest):
        return NoRecipe(f"needs an argument only you can fill in: {bad!r}")
    pub = registry.pypi(base, version or None)
    if not pub:
        return NoRecipe(f"PyPI package {base} is not published")
    if foreign := _owns(ev, derived_from, f"PyPI package {base}", pub):
        return foreign
    # extras ride along in the install spec ("pkg[mcp]"); the command defaults to the name
    return _recipe(ev, derived_from, Install(kind="pypi", package=spec, version=pub.version),
                   [command or base], rest, env)


def _uvx(ev, registry, derived_from, args, env) -> Recipe | NoRecipe:
    args = [a for a in args if a not in ("-q", "--quiet")]
    if args[:1] == ["--from"] and len(args) >= 3:
        return _pypi(ev, registry, derived_from, args[1], args[2], args[3:], env)
    if not args:
        return NoRecipe("uvx with no package")
    spec = args[0]
    m = re.match(r"^([A-Za-z0-9._-]+)(\[[A-Za-z0-9._,-]+\])?(?:@([A-Za-z0-9._-]+))?$", spec)
    if not m:
        return NoRecipe(f"not a uvx package: {spec!r}")
    pkg = m.group(1) + (m.group(2) or "") + (f"=={m.group(3)}" if m.group(3) and m.group(3) != "latest" else "")
    return _pypi(ev, registry, derived_from, pkg, m.group(1), args[1:], env)


_DOCKER_FLAGS_WITH_VALUE = {"-e", "--env", "-v", "--volume", "--name", "-p", "--publish",
                            "--network", "--net", "-w", "--workdir", "--user", "-u",
                            "--env-file", "--mount", "--entrypoint", "--platform", "-l", "--label"}


def _docker(ev, derived_from, args, env) -> Recipe | NoRecipe:
    if args[:1] != ["run"]:
        return NoRecipe("docker command is not `docker run`")
    i, env = 1, list(env)
    while i < len(args):
        a = args[i]
        if a in ("-e", "--env") and i + 1 < len(args):
            name = args[i + 1].split("=", 1)[0]
            if _ENV_NAME.match(name):
                env.append(EnvVar(name=name, required=True, secret=_looks_secret(name)))
            i += 2
            continue
        if a in ("-v", "--volume", "--mount", "--env-file"):
            return NoRecipe("docker run mounts something from your machine")
        if a in _DOCKER_FLAGS_WITH_VALUE:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if i >= len(args):
        return NoRecipe("docker run names no image")
    image, rest = args[i], args[i + 1:]
    if not _IMAGE.match(image):
        return NoRecipe(f"not an image reference: {image!r}")
    owner = ev.repo.split("/")[0].lower()
    parts = image.split("@")[0].split(":")[0].lower().split("/")
    namespace = parts[1] if len(parts) >= 3 else (parts[0] if len(parts) == 2 else "")
    if namespace != owner:
        return NoRecipe(f"image {image} isn't published under {owner}, so it can't be tied to this repository")
    if bad := _placeholder(rest):
        return NoRecipe(f"needs an argument only you can fill in: {bad!r}")
    return _recipe(ev, derived_from, Install(kind="oci", image=image), [], rest, env)


def _looks_secret(name: str) -> bool:
    return bool(re.search(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|PAT|CREDENTIAL|AUTH)", name, re.I))


def _from_launch(ev, registry, derived_from, command, args, env) -> Recipe | NoRecipe:
    base = command.rsplit("/", 1)[-1]
    if base == "npx":
        rest = [a for a in args if a not in ("-y", "--yes", "-q")]
        if not rest:
            return NoRecipe("npx with no package")
        if rest[0] in ("-p", "--package") and len(rest) >= 3:
            return _npm(ev, registry, derived_from, rest[1], rest[3:], env)
        return _npm(ev, registry, derived_from, rest[0], rest[1:], env)
    if base == "uvx":
        return _uvx(ev, registry, derived_from, args, env)
    if base == "uv" and args[:2] == ["tool", "run"]:
        return _uvx(ev, registry, derived_from, args[2:], env)
    if base == "docker":
        return _docker(ev, derived_from, args, env)
    return NoRecipe(f"launched with `{base}` from a local copy, not from a registry")


# --- 1. server.json ---------------------------------------------------------------------


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default


def _from_server_json(ev: Evidence, registry: Registry) -> Recipe | NoRecipe | None:
    if not ev.server_json:
        return None
    try:
        data = json.loads(ev.server_json)
    except ValueError:
        return NoRecipe("server.json is not valid JSON")
    packages = data.get("packages") or []
    if not packages:
        return NoRecipe("server.json lists no packages (remote only)")
    for p in packages:
        kind = str(_pick(p, "registryType", "registry_type", "registry_name", default="")).lower()
        ident = _pick(p, "identifier", "name", default="")
        version = _pick(p, "version", default=None)
        transport = _pick(p, "transport", default={"type": "stdio"})
        ttype = transport.get("type") if isinstance(transport, dict) else str(transport)
        if ttype != "stdio":
            continue
        env = []
        for e in _pick(p, "environmentVariables", "environment_variables", default=[]) or []:
            name = e.get("name", "")
            if _ENV_NAME.match(name):
                env.append(EnvVar(
                    name=name,
                    required=bool(_pick(e, "isRequired", "is_required", default=False)),
                    secret=bool(_pick(e, "isSecret", "is_secret", default=_looks_secret(name))),
                    description=str(e.get("description", ""))[:200],
                ))
        args = []
        for a in _pick(p, "packageArguments", "package_arguments", default=[]) or []:
            value = _pick(a, "value", "default", default=None)
            if value is None:
                if a.get("isRequired") or a.get("is_required"):
                    return NoRecipe(f"server.json needs an argument only you can fill in: {a.get('name') or a.get('valueHint')!r}")
                continue
            if a.get("type") == "named" and a.get("name"):
                args += [a["name"], str(value)]
            else:
                args.append(str(value))
        if kind == "npm":
            return _npm(ev, registry, "server.json", f"{ident}@{version}" if version else ident, args, env)
        if kind == "pypi":
            return _pypi(ev, registry, "server.json", f"{ident}=={version}" if version else ident, None, args, env)
        if kind in ("oci", "docker"):
            image = ident if (":" in ident.rsplit("/", 1)[-1] or not version) else f"{ident}:{version}"
            if not _IMAGE.match(image):
                return NoRecipe(f"server.json image is not a valid reference: {image!r}")
            if bad := _placeholder(args):
                return NoRecipe(f"needs an argument only you can fill in: {bad!r}")
            return _recipe(ev, "server.json", Install(kind="oci", image=image), [], args, env)
    return NoRecipe("server.json has no stdio package from npm, PyPI or a container registry")


# --- 2. README mcpServers block ---------------------------------------------------------


def _balanced_object(text: str, start: int) -> str | None:
    depth, i, in_str, esc = 0, start, False, False
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return None


def _loads_lenient(s: str):
    s = re.sub(r"(?m)^\s*//.*$", "", s)
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return json.loads(s)


def mcp_server_blocks(readme: str) -> list[dict]:
    """Every server entry in every "mcpServers" block, in document order."""
    out = []
    for m in re.finditer(r'"mcpServers"\s*:\s*\{', readme):
        obj = _balanced_object(readme, m.end() - 1)
        if not obj:
            continue
        try:
            servers = _loads_lenient(obj)
        except ValueError:
            continue
        for v in servers.values() if isinstance(servers, dict) else []:
            if isinstance(v, dict) and isinstance(v.get("command"), str):
                out.append(v)
    return out


def _from_readme(ev: Evidence, registry: Registry) -> Recipe | NoRecipe | None:
    if not ev.readme:
        return None
    blocks = mcp_server_blocks(ev.readme)
    if not blocks:
        return None
    last: NoRecipe | None = None
    for b in blocks:
        args = [str(a) for a in b.get("args") or []]
        env = []
        for name in (b.get("env") or {}):
            if _ENV_NAME.match(name):
                env.append(EnvVar(name=name, required=True, secret=_looks_secret(name)))
        out = _from_launch(ev, registry, "readme-config", b["command"], args, env)
        if isinstance(out, Recipe):
            return out
        last = out
    return last


# --- 3. package manifest ----------------------------------------------------------------


def _from_manifest(ev: Evidence, registry: Registry) -> Recipe | NoRecipe | None:
    if ev.package_json:
        try:
            pkg = json.loads(ev.package_json)
        except ValueError:
            pkg = {}
        deps = {**(pkg.get("dependencies") or {})}
        if "@modelcontextprotocol/sdk" in deps or "fastmcp" in deps:
            name = pkg.get("name")
            if pkg.get("private") or not name:
                return NoRecipe("package.json is private or unnamed, so it isn't on npm")
            if not pkg.get("bin"):
                return NoRecipe("package.json depends on the MCP SDK but declares no command")
            return _npm(ev, registry, "package-manifest", name, [], [])
    if ev.pyproject:
        try:
            proj = tomllib.loads(ev.pyproject).get("project") or {}
        except tomllib.TOMLDecodeError:
            proj = {}
        deps = [re.split(r"[\s<>=!~\[;]", d, maxsplit=1)[0].lower() for d in proj.get("dependencies") or []]
        if "mcp" in deps or "fastmcp" in deps:
            name, scripts = proj.get("name"), proj.get("scripts") or {}
            if not name:
                return NoRecipe("pyproject.toml has no project name")
            if not scripts:
                return NoRecipe("pyproject.toml depends on MCP but declares no command")
            if len(scripts) == 1:
                cmd = next(iter(scripts))
            else:
                mcp = [s for s in scripts if "mcp" in s.lower() or s == name]
                if len(mcp) != 1:
                    return NoRecipe(f"pyproject.toml has several commands ({', '.join(sorted(scripts))})")
                cmd = mcp[0]
            return _pypi(ev, registry, "package-manifest", name, cmd, [], [])
    return None
