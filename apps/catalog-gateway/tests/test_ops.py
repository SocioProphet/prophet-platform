"""Catalog operational-plane capture tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

client = TestClient(app)

ASSET = {
    "asset_id": "asset-ops-001", "asset_kind": "dataset", "tenant_id": "t",
    "distribution_class": "public_derived", "source_refs": ["src-1"],
    "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z",
}


def _seed(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("CATALOG_OPS_CAPTURE", "true")
    d = tmp_path / "prophet-platform" / "catalog" / "asset"
    d.mkdir(parents=True, exist_ok=True)
    (d / "asset-ops-001.json").write_text(json.dumps(ASSET), encoding="utf-8")


def _events(tmp_path) -> list[dict]:
    ev = tmp_path / "prophet-platform" / "events" / "catalog-gateway"
    return [json.loads(p.read_text()) for p in sorted(ev.glob("*.event.json"))] if ev.exists() else []


def test_emit_is_best_effort_on_nonserializable_record(monkeypatch, tmp_path):
    # A non-JSON-serializable value (e.g. a set) must not raise into the caller —
    # emit() returns None rather than breaking the read path it observes.
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("CATALOG_OPS_CAPTURE", "true")
    from app import ops
    assert ops.emit("catalog.resolved.v0", {"kind": "asset", "bad": {1, 2, 3}}) is None
    assert _events(tmp_path) == []


def test_resolve_hit_is_captured(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/asset/asset-ops-001").status_code == 200
    evs = _events(tmp_path)
    resolved = [e for e in evs if e["event_type"] == "catalog.resolved.v0"]
    assert resolved and resolved[0]["event"]["hit"] is True
    assert resolved[0]["event"]["entry_id"] == "asset-ops-001"
    assert resolved[0]["event"]["producer"] == "catalog-gateway"


def test_resolve_miss_is_captured(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/asset/nope").status_code == 404
    misses = [e for e in _events(tmp_path) if e["event_type"] == "catalog.resolved.v0" and e["event"]["hit"] is False]
    assert misses and misses[0]["event"]["entry_id"] == "nope"


def test_dcat_emission_is_captured(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/asset/asset-ops-001.dcat.json").status_code == 200
    dcat = [e for e in _events(tmp_path) if e["event_type"] == "catalog.dcat.emitted.v0"]
    assert dcat and dcat[0]["event"]["asset_id"] == "asset-ops-001"
    assert dcat[0]["event"]["access_rights"] == "public"  # public_derived -> public
    assert dcat[0]["event"]["distribution_class"] == "public_derived"


def test_capture_can_be_disabled(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    monkeypatch.setenv("CATALOG_OPS_CAPTURE", "false")
    assert client.get("/v1/catalog/asset/asset-ops-001").status_code == 200
    assert _events(tmp_path) == []  # nothing captured when off
