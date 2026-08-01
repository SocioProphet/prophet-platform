from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import attention_registry as ar  # type: ignore
import connector_roots as cr  # type: ignore
import rail_orchestrator as ro  # type: ignore

LANE = ROOT / "contracts" / "workspace-control-plane"
MARK_SCHEMA = json.loads((LANE / "schemas" / "attention-mark.v0.schema.json").read_text())

NOW = "2026-08-01T00:00:00+00:00"


def _root(mode):
    return {"root_id": f"root-{mode}", "account_ref": "a", "kind": "local_dir",
            "sync_mode": mode, "cache_policy": "full", "allowed_actions": ["read"], "delta_cursor": None}


# ---- rail orchestrator ----

def test_orchestrate_honors_rails(tmp_path):
    (tmp_path / "f.txt").write_text("hi")
    conn = cr.LocalFilesConnector(str(tmp_path))
    roots = [_root("mirror"), _root("live"), _root("action")]
    connectors = {r["root_id"]: conn for r in roots}

    results = {res.root_id: res for res in ro.orchestrate(roots, connectors, now=NOW)}
    assert len(results["root-mirror"].assets) == 1 and len(results["root-mirror"].events) == 1
    assert results["root-live"].assets == [] and len(results["root-live"].events) == 1
    assert results["root-action"].deferred_to_workflow and results["root-action"].events == []


def test_apply_cursors_advances_root(tmp_path):
    (tmp_path / "f.txt").write_text("hi")
    conn = cr.LocalFilesConnector(str(tmp_path))
    roots = [_root("mirror")]
    results = ro.orchestrate(roots, {roots[0]["root_id"]: conn}, now=NOW)
    ro.apply_cursors(roots, results)
    assert roots[0]["delta_cursor"] is not None


def test_missing_connector_raises():
    with pytest.raises(KeyError):
        ro.orchestrate([_root("mirror")], {}, now=NOW)


# ---- attention registry ----

def mark(mark_id, mode, *, triggers=None, half_life=None, suppress=None, created_at="2026-07-01T00:00:00+00:00"):
    m = {"mark_id": mark_id, "target_ref": "asset://x", "mode": mode, "created_at": created_at}
    if triggers is not None:
        m["resurfacing_triggers"] = triggers
    if half_life is not None:
        m["decay"] = {"policy": "exponential", "half_life_seconds": half_life}
    if suppress is not None:
        m["suppression"] = {"rules": suppress}
    return m


def test_marks_conform_to_schema():
    for m in (mark("mark-0001", "pin"), mark("mark-0002", "watch", triggers=["related_asset_ingested"]),
              mark("mark-0003", "incubate", half_life=3600, suppress=["focus_mode"])):
        assert list(Draft202012Validator(MARK_SCHEMA).iter_errors(m)) == [], m


def test_pin_always_and_forget_hold_never():
    assert ar.should_surface(mark("m", "pin"), NOW)
    assert not ar.should_surface(mark("m", "forget"), NOW)
    assert not ar.should_surface(mark("m", "hold", triggers=["e"]), NOW, active_events={"e"})


def test_watch_needs_event():
    m = mark("m", "watch", triggers=["related_asset_ingested"])
    assert not ar.should_surface(m, NOW)
    assert ar.should_surface(m, NOW, active_events={"related_asset_ingested"})


def test_revisit_time_trigger():
    m = mark("m", "revisit", triggers=["at:2026-07-15T00:00:00+00:00"])
    assert ar.should_surface(m, NOW)  # now is after the scheduled time
    future = mark("m", "revisit", triggers=["at:2026-12-01T00:00:00+00:00"])
    assert not ar.should_surface(future, NOW)


def test_incubate_surfaces_after_half_life():
    # created 2026-07-01, half-life 1 day -> due by 2026-08-01.
    due = mark("m", "incubate", half_life=86400, created_at="2026-07-01T00:00:00+00:00")
    assert ar.should_surface(due, NOW)
    not_due = mark("m", "incubate", half_life=86400, created_at="2026-07-31T23:00:00+00:00")
    assert not ar.should_surface(not_due, NOW)


def test_suppression_wins():
    m = mark("m", "pin", suppress=["focus_mode"])
    assert not ar.should_surface(m, NOW, active_suppressions={"focus_mode"})


def test_registry_resolves_and_transitions():
    reg = ar.AttentionRegistry()
    reg.add(mark("a-pin", "pin"))
    reg.add(mark("b-hold", "hold", triggers=["e"]))
    reg.add(mark("c-watch", "watch", triggers=["e"]))
    surfaced = [m["mark_id"] for m in reg.resolve_surfacing(NOW, active_events={"e"})]
    assert surfaced == ["a-pin", "c-watch"]  # hold stays down; stable order

    reg.release("b-hold", "watch")  # release the hold
    surfaced2 = [m["mark_id"] for m in reg.resolve_surfacing(NOW, active_events={"e"})]
    assert "b-hold" in surfaced2

    reg.forget("a-pin")
    assert "a-pin" not in [m["mark_id"] for m in reg.resolve_surfacing(NOW, active_events={"e"})]
