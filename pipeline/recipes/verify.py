"""Verify a recipe: build it, start it confined, and ask it for its tools over MCP.

The image comes from a fixed template per install kind, never from the repository's own
Dockerfile, and the exact Dockerfile is stored in the recipe so ONEXUS builds the same
thing. Network is used only while installing the package. The server is then started
with the flags ONEXUS's confine.py uses (no network, read-only root, no capabilities, a
non-root user, limits) and sent `initialize` and `tools/list`. A recipe counts as
installable only if that handshake answers.

The host scan reads the package's own installed files (not its dependencies) for
`https://host` literals, drops documentation, schema and example hosts, and adds hosts
implied by well-known variables. Those are proposals; ONEXUS asks the person to approve
them at install time.
"""
from __future__ import annotations

import json
import queue
import re
import secrets
import subprocess
import threading
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime

from pipeline.recipes.schema import Hosts, Recipe, Verified

NODE_BASE = "node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392"
PYTHON_BASE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
# Full images with compilers, used only to build packages that compile native code; the
# result is copied into the slim runtime. Same Node and Python versions as the slim pins.
NODE_BUILD = "node:22@sha256:0e5f906573693feaa1e21057ebdcfdb5bd5021f050b2dc7c9deceb629c7da2a8"
PYTHON_BUILD = "python:3.12@sha256:42dc0ee40d7707e2f2ee506a1cbe52e09ab11c207c5b429342638f83177601fe"
_NEEDS_COMPILER = re.compile(r"gyp ERR!|Failed building wheel|failed-wheel-build|error: command '[^']*(gcc|cc|g\+\+)'|"
                             r"No such file or directory: '(gcc|cc|g\+\+)'|Rust compiler|cargo|"
                             r"pkg-config|Python\.h: No such file", re.I)
PLACEHOLDER = "onexus-verify-placeholder"
EXIT_MEANING = {
    1: "it reported an error",
    126: "its command isn't executable",
    127: "its command wasn't found in the image",
    132: "illegal instruction: a native library needs CPU features this machine lacks",
    134: "it aborted",
    137: "it was killed, most likely by the 1 GB memory limit",
    139: "it crashed (segmentation fault)",
}

CONFINE_FLAGS = [
    "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m,mode=1777",
    "--tmpfs", "/work:rw,size=256m,uid=65534,gid=65534", "-w", "/work", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges", "--user", "65534:65534",
    "--memory", "1g", "--cpus", "1", "--pids-limit", "256", "-e", "HOME=/work",
]

# Variables whose service is unambiguous. Anything tenant-specific (Jira, a self-hosted
# GitLab) is left out on purpose: the person adds those hosts themselves.
ENV_HOSTS = {
    "GITHUB_TOKEN": "api.github.com", "GITHUB_PERSONAL_ACCESS_TOKEN": "api.github.com",
    "GH_TOKEN": "api.github.com", "SLACK_BOT_TOKEN": "slack.com", "SLACK_TOKEN": "slack.com",
    "NOTION_API_KEY": "api.notion.com", "NOTION_TOKEN": "api.notion.com",
    "OPENAI_API_KEY": "api.openai.com", "ANTHROPIC_API_KEY": "api.anthropic.com",
    "BRAVE_API_KEY": "api.search.brave.com", "TAVILY_API_KEY": "api.tavily.com",
    "EXA_API_KEY": "api.exa.ai", "FIRECRAWL_API_KEY": "api.firecrawl.dev",
    "GEMINI_API_KEY": "generativelanguage.googleapis.com",
    "LINEAR_API_KEY": "api.linear.app", "STRIPE_SECRET_KEY": "api.stripe.com",
    "STRIPE_API_KEY": "api.stripe.com", "SENTRY_AUTH_TOKEN": "sentry.io",
    "CLOUDFLARE_API_TOKEN": "api.cloudflare.com", "SUPABASE_ACCESS_TOKEN": "api.supabase.com",
    "HF_TOKEN": "huggingface.co", "PERPLEXITY_API_KEY": "api.perplexity.ai",
    "MISTRAL_API_KEY": "api.mistral.ai", "GROQ_API_KEY": "api.groq.com",
    "DISCORD_TOKEN": "discord.com", "DISCORD_BOT_TOKEN": "discord.com",
    "TELEGRAM_BOT_TOKEN": "api.telegram.org",
}

_NOT_A_SERVICE = re.compile(
    r"(^|\.)(localhost|example\.(com|org|net)|json-schema\.org|w3\.org|xmlns\.com|"
    r"schemas?\.[a-z.]+|modelcontextprotocol\.io|spec\.modelcontextprotocol\.io|"
    r"npmjs\.(com|org)|nodejs\.org|pypi\.org|python\.org|docs\.python\.org|"
    r"developer\.mozilla\.org|mozilla\.org|opensource\.org|spdx\.org|apache\.org|"
    r"creativecommons\.org|githubusercontent\.com|semver\.org|"
    r"tc39\.es|ecma-international\.org|unicode\.org|ietf\.org|rfc-editor\.org|"
    r"shields\.io|badge\.fury\.io|jsdelivr\.net|unpkg\.com|readthedocs\.io|"
    r"stackoverflow\.com|wikipedia\.org|yaml\.org|json\.org|"
    r"[a-z0-9-]+\.(local|internal|test|invalid|example))$"
)
# Exact names only: api.github.com is a service even though github.com links are docs.
_DOC_EXACT = {"github.com", "www.github.com", "gist.github.com", "docs.github.com"}
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_IP = re.compile(r"^\d+(\.\d+){3}$")


# Docker on Apple Silicon (seen on an M5 Pro) reports SVE2 without base SVE, and OpenSSL
# builds that dispatch on it die with SIGILL on import (cryptography 48+, which mcp 2.x
# loads at import). Masking only the SVE bits keeps NEON, AES and SHA acceleration. On x86
# OpenSSL reads OPENSSL_ia32cap instead, so this changes nothing there.
OPENSSL_ENV = "ENV OPENSSL_armcap=0x1fff\n"


def not_a_service(host: str) -> bool:
    return host in _DOC_EXACT or bool(_NOT_A_SERVICE.search(host))


def dockerfile(recipe: Recipe, native: bool = False) -> str | None:
    i = recipe.install
    if native and i.kind == "npm":
        return (f"FROM {NODE_BUILD} AS build\n"
                f"RUN npm install -g --omit=dev --no-fund --no-audit {i.package}@{i.version} "
                f"&& npm cache clean --force\n"
                f"FROM {NODE_BASE}\n"
                + OPENSSL_ENV +
                "COPY --from=build /usr/local/lib/node_modules /usr/local/lib/node_modules\n"
                "COPY --from=build /usr/local/bin /usr/local/bin\n"
                "USER 65534:65534\n")
    if native and i.kind == "pypi":
        return (f"FROM {PYTHON_BUILD} AS build\n"
                f"RUN pip wheel --no-cache-dir --disable-pip-version-check --wheel-dir /wheels "
                f"{i.package}=={i.version}\n"
                f"FROM {PYTHON_BASE}\n"
                + OPENSSL_ENV +
                f"ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n"
                f"COPY --from=build /wheels /wheels\n"
                f"RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check "
                f"--no-index --find-links /wheels {i.package}=={i.version} && rm -rf /wheels\n"
                f"USER 65534:65534\n")
    if i.kind == "npm":
        return (f"FROM {NODE_BASE}\n"
                + OPENSSL_ENV +
                f"RUN npm install -g --omit=dev --no-fund --no-audit {i.package}@{i.version} "
                f"&& npm cache clean --force\n"
                f"USER 65534:65534\n")
    if i.kind == "pypi":
        return (f"FROM {PYTHON_BASE}\n"
                + OPENSSL_ENV +
                f"ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n"
                f"RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check "
                f"{i.package}=={i.version}\n"
                f"USER 65534:65534\n")
    return None


def image_tag(recipe: Recipe) -> str:
    v = (recipe.install.version or "x").replace("+", "-")
    return f"onexus-verify/{recipe.slug}:{v}"


def run_argv(image: str, recipe: Recipe, env_values: dict[str, str], name: str | None = None) -> list[str]:
    argv = ["docker", "run", "--rm", "-i", *(["--name", name] if name else []), *CONFINE_FLAGS]
    for k, v in env_values.items():
        argv += ["-e", f"{k}={v}"]
    return argv + [image, *recipe.command, *recipe.args]


def _build(recipe: Recipe, timeout: int) -> tuple[str | None, str]:
    """Returns (image reference, error)."""
    if recipe.install.kind == "oci":
        ref = recipe.install.image
        p = subprocess.run(["docker", "pull", "-q", ref], capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None, (p.stderr or p.stdout).strip()[-500:]
        d = subprocess.run(["docker", "inspect", "--format", "{{index .RepoDigests 0}}", ref],
                           capture_output=True, text=True, timeout=60)
        digest = d.stdout.strip().rsplit("@", 1)[-1] if d.returncode == 0 and "@" in d.stdout else None
        recipe.install.digest = digest
        return (f"{ref.split('@')[0]}@{digest}" if digest else ref), ""
    tag = image_tag(recipe)
    log = ""
    for native in (False, True):
        text = dockerfile(recipe, native=native)
        p = subprocess.run(["docker", "build", "--progress=plain", "-t", tag, "-"], input=text,
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode == 0:
            recipe.dockerfile = text
            return tag, ""
        log = (p.stderr or p.stdout)
        if native or not _NEEDS_COMPILER.search(log):
            break
    lines = [ln for ln in log.splitlines() if re.search(r"(npm error|ERROR|error:|ERR!)", ln)]
    return None, "\n".join(lines[-8:])[-800:] or log.strip()[-800:]


def handshake(argv: list[str], timeout: float = 60.0) -> dict:
    """Start the server, send initialize + tools/list, return what it said."""
    t0 = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(ln) for ln in iter(proc.stdout.readline, b"")] or lines.put(None),
                     daemon=True).start()
    err_tail: list[bytes] = []
    err_reader = threading.Thread(target=lambda: [err_tail.append(ln) for ln in iter(proc.stderr.readline, b"")],
                                  daemon=True)
    err_reader.start()

    def send(msg):
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        proc.stdin.flush()

    def wait_for(rid):
        while True:
            left = timeout - (time.monotonic() - t0)
            if left <= 0:
                raise TimeoutError(f"no answer within {int(timeout)}s")
            try:
                line = lines.get(timeout=left)
            except queue.Empty:
                raise TimeoutError(f"no answer within {int(timeout)}s") from None
            if line is None:
                raise EOFError("the server exited")
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # a log line on stdout
            if isinstance(msg, dict) and msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"])[:300])
                return msg.get("result") or {}

    out: dict = {"stage": "start"}
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "onexus-verify", "version": "1"}}})
        init = wait_for(1)
        out["stage"] = "handshake"
        info = init.get("serverInfo") or {}
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = wait_for(2).get("tools") or []
        out.update(ok=True, stage="done", tools=sorted(t.get("name", "") for t in tools if t.get("name")),
                   ms=int((time.monotonic() - t0) * 1000),
                   server_name=str(info.get("name", ""))[:100], server_version=str(info.get("version", ""))[:50])
    except (TimeoutError, EOFError, RuntimeError, BrokenPipeError, OSError) as exc:
        if isinstance(exc, (EOFError, BrokenPipeError)):
            try:
                proc.wait(timeout=5)  # let it finish writing, then collect what it said
            except subprocess.TimeoutExpired:
                pass
            err_reader.join(timeout=2)
        tail = b"".join(err_tail[-8:]).decode(errors="replace").strip()
        why = str(exc)
        code = proc.poll()
        if isinstance(exc, EOFError) and code is not None:
            why = f"the server exited with code {code}"
            if code in EXIT_MEANING:
                why += f" ({EXIT_MEANING[code]})"
        out.update(ok=False, reason=(f"{why}. " + tail[-400:]).strip())
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    return out


_SCAN_NPM = r"""cd "$(npm root -g)/{pkg}" 2>/dev/null && grep -rInoE 'https?://[A-Za-z0-9.-]+' --exclude-dir=node_modules --include='*.js' --include='*.mjs' --include='*.cjs' --include='*.json' . 2>/dev/null | head -4000"""
_SCAN_PYPI = r"""
import importlib.metadata as m, re, sys
pat = re.compile(r'https?://([A-Za-z0-9.-]+)')
try:
    files = m.distribution(sys.argv[1]).files or []
except Exception:
    files = []
n = 0
for f in files:
    if not str(f).endswith(('.py', '.json', '.toml', '.yaml', '.yml')):
        continue
    try:
        text = f.locate().read_text(errors='ignore')
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        for h in pat.findall(line):
            print(f'{f}:{i}:https://{h}'); n += 1
    if n > 4000:
        break
"""


def scan_hosts(image: str, recipe: Recipe) -> Hosts:
    found: dict[str, list[str]] = defaultdict(list)
    counts: Counter = Counter()
    if recipe.install.kind == "npm":
        cmd = ["sh", "-c", _SCAN_NPM.format(pkg=recipe.install.package)]
    elif recipe.install.kind == "pypi":
        cmd = ["python", "-c", _SCAN_PYPI, recipe.install.package.split("[")[0]]
    else:
        cmd = None
    if cmd:
        p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", cmd[0], image, *cmd[1:]],
                           capture_output=True, text=True, timeout=120)
        for line in p.stdout.splitlines():
            loc, _, url = line.rpartition(":http")
            host = url.split("//", 1)[-1].lower().rstrip(".")
            if not _HOST.match(host) or _IP.match(host) or not_a_service(host):
                continue
            counts[host] += 1
            if len(found[host]) < 3:
                found[host].append(loc.lstrip("./"))
    for e in recipe.env:
        if e.name in ENV_HOSTS:
            h = ENV_HOSTS[e.name]
            counts[h] += 1000
            found[h].insert(0, f"env {e.name}")
    proposed = [h for h, _ in counts.most_common(10)]
    return Hosts(proposed=proposed, evidence={h: found[h] for h in proposed})


_SCRIPTS = r"""
import importlib.metadata as m, sys
d = m.distribution(sys.argv[1])
print("\n".join(e.name for e in d.entry_points if e.group == "console_scripts"))
"""


def _pypi_command(image: str, recipe: Recipe) -> None:
    """If the recipe's command isn't one the installed package declares, use the one it
    does declare (exactly one, or exactly one with "mcp" in its name)."""
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image,
                        "-c", _SCRIPTS, recipe.install.package.split("[")[0]],
                       capture_output=True, text=True, timeout=120)
    scripts = [x for x in p.stdout.split() if x]
    if not scripts or (recipe.command and recipe.command[0] in scripts):
        return
    pick = scripts if len(scripts) == 1 else [x for x in scripts if "mcp" in x.lower()]
    if len(pick) == 1:
        recipe.command = [pick[0], *recipe.command[1:]]


def verify(recipe: Recipe, *, build_timeout: int = 900, handshake_timeout: float = 60.0,
           keep_image: bool = False) -> Recipe:
    now = datetime.now(UTC)
    image, err = _build(recipe, build_timeout)
    if not image:
        recipe.verified = Verified(at=now, ok=False, stage="build", reason=err or "build failed")
        return recipe
    try:
        if recipe.install.kind == "pypi":
            _pypi_command(image, recipe)
        env_values = {e.name: PLACEHOLDER for e in recipe.env if e.required}
        # Named, so it can be removed: killing the docker client doesn't stop a container.
        name = f"onexus-verify-{recipe.slug}-{secrets.token_hex(3)}"
        try:
            res = handshake(run_argv(image, recipe, env_values, name=name), timeout=handshake_timeout)
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
        if res.get("ok") and not res["tools"]:
            recipe.verified = Verified(at=now, ok=False, stage="handshake",
                                       reason="it started and answered, but offers no tools")
        elif res.get("ok"):
            recipe.verified = Verified(at=now, ok=True, tools=res["tools"], handshake_ms=res["ms"],
                                       server_name=res["server_name"], server_version=res["server_version"])
            recipe.hosts = scan_hosts(image, recipe)
        else:
            recipe.verified = Verified(at=now, ok=False, stage=res["stage"], reason=res.get("reason", ""))
    finally:
        if not keep_image:
            subprocess.run(["docker", "rmi", "-f", image], capture_output=True, timeout=120)
    return recipe
