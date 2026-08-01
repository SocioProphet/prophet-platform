from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import connector_roots as cr  # type: ignore

LANE = ROOT / "contracts" / "workspace-control-plane"
ASSET_SCHEMA = json.loads((LANE / "schemas" / "asset.v0.schema.json").read_text())
EVENT_SCHEMA = json.loads((LANE / "schemas" / "event.v0.schema.json").read_text())


def _valid(schema, obj):
    return list(Draft202012Validator(schema).iter_errors(obj)) == []


def _root(tmp, mode="mirror"):
    return {"root_id": "root-local-test", "account_ref": "acct-local", "kind": "local_dir",
            "sync_mode": mode, "cache_policy": "full", "allowed_actions": ["read"], "delta_cursor": None}


def test_local_mirror_produces_valid_assets_and_events(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world")

    conn = cr.LocalFilesConnector(str(tmp_path))
    assets, events, cursor = conn.sync(_root(tmp_path, "mirror"))

    assert len(assets) == 2 and len(events) == 2
    for a in assets:
        assert _valid(ASSET_SCHEMA, a), a
        assert a["current_version"]["content_hash"].startswith("sha256:")
    for e in events:
        assert _valid(EVENT_SCHEMA, e), e
        assert e["activity"] == "AssetIngested"
    assert cursor is not None


def test_incremental_cursor_skips_unchanged(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    conn = cr.LocalFilesConnector(str(tmp_path))
    _, _, cursor = conn.sync(_root(tmp_path))
    # Second sync from the returned cursor: nothing changed -> nothing ingested.
    assets2, events2, cursor2 = conn.sync(_root(tmp_path), since_cursor=cursor)
    assert assets2 == [] and events2 == []


def test_live_rail_emits_events_without_cached_assets(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    conn = cr.LocalFilesConnector(str(tmp_path))
    assets, events, _ = conn.sync(_root(tmp_path, "live"))
    assert assets == [] and len(events) == 1  # live = just-in-time, no cached copy


def test_action_rail_does_not_ingest(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    conn = cr.LocalFilesConnector(str(tmp_path))
    assets, events, _ = conn.sync(_root(tmp_path, "action"))
    assert assets == [] and events == []


def test_cloud_connectors_are_credential_gated():
    for provider, cls in cr.CLOUD_CONNECTORS.items():
        conn = cls()
        with pytest.raises(NotImplementedError) as exc:
            conn.sync({"root_id": "r"})
        # The delta mechanism is named even though it is not wired.
        assert conn.delta_mechanism and conn.delta_mechanism in str(exc.value)
