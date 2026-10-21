"""Hand-written adapters only make an agent runnable when they can actually run.

A descriptor under adapters/ that points at `python -m adapters.<name>.server` needs that
server beside it, and one that names some other command needs that command to exist. A
descriptor that has neither says `"status": "planned"`, and no catalog entry is runnable
through it, now or after a rebuild.
"""
from __future__ import annotations

import json

from pipeline.build import adapter_unavailable, merge_overrides
from pipeline.paths import ADAPTERS_DIR, CATALOG_DIR
from pipeline.schema import Agent


def _descriptors():
    for f in sorted(ADAPTERS_DIR.glob("*/mcp.json")):
        yield f, json.loads(f.read_text())


def test_every_descriptor_is_runnable_or_marked_planned():
    for f, d in _descriptors():
        if d.get("status") == "planned":
            assert d.get("status_note"), f"{f} is planned but doesn't say why"
            continue
        args = d.get("args", [])
        if d.get("command") == "python" and args[:1] == ["-m"]:
            assert (f.parent / "server.py").exists(), f"{f} points at a server that isn't there"
        assert d.get("confinement"), f"{f} runs but declares no confinement"


def test_no_catalog_entry_is_runnable_through_a_planned_adapter():
    bad = []
    for f in CATALOG_DIR.glob("*/*.json"):
        d = json.loads(f.read_text())
        if d.get("runnable") and adapter_unavailable(d.get("adapter_ref")):
            bad.append(f.name)
    assert bad == []


def test_adapter_unavailable():
    assert adapter_unavailable("adapters/aider/mcp.json")
    assert adapter_unavailable("adapters/does-not-exist/mcp.json")
    assert not adapter_unavailable("adapters/haystack/mcp.json")
    assert not adapter_unavailable("mcp/stdio")
    assert not adapter_unavailable(None)


def test_a_rebuild_does_not_restore_runnable_from_a_planned_adapter():
    raw = json.loads((CATALOG_DIR / "coding" / "aider.json").read_text())
    prior = Agent.model_validate({**raw, "runnable": True, "adapter_ref": "adapters/aider/mcp.json"})
    target = Agent.model_validate({**raw, "runnable": False, "adapter_ref": None})
    merge_overrides(target, prior)
    assert (target.runnable, target.adapter_ref) == (False, None)
