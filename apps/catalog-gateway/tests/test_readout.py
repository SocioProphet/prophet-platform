"""Catalog operational-plane analysis-layer tests (the readout fold)."""
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
    "asset_id": "asset-ro-1", "asset_kind": "dataset", "tenant_id": "t",
    "distribution_class": "public_derived", "source_refs": ["src-1"],
    "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z",
}
SOURCE_HOT = {"source_id": "src-1", "tenant_id": "t"}
SOURCE_COLD = {"source_id": "src-cold", "tenant_id": "t"}


def _seed(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("CATALOG_OPS_CAPTURE", "true")
    root = tmp_path / "prophet-platform" / "catalog"
    (root / "asset").mkdir(parents=True, exist_ok=True)
    (root / "source").mkdir(parents=True, exist_ok=True)
    (root / "asset" / "asset-ro-1.json").write_text(json.dumps(ASSET), encoding="utf-8")
    (root / "source" / "src-1.json").write_text(json.dumps(SOURCE_HOT), encoding="utf-8")
    (root / "source" / "src-cold.json").write_text(json.dumps(SOURCE_COLD), encoding="utf-8")


def _drive(monkeypatch, tmp_path):
    """Produce a known event mix: 2 hits on the asset, 1 hit on src-1, 3 misses on the
    same absent id, and 1 DCAT emission."""
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/asset/asset-ro-1").status_code == 200
    assert client.get("/v1/catalog/asset/asset-ro-1").status_code == 200
    assert client.get("/v1/catalog/source/src-1").status_code == 200
    for _ in range(3):
        assert client.get("/v1/catalog/asset/ghost").status_code == 404
    assert client.get("/v1/catalog/asset/asset-ro-1.dcat.json").status_code == 200


def test_zero_readout_is_well_formed(monkeypatch, tmp_path):
    # No events, no catalog → a valid zero readout, never an error.
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    from app import readout
    r = readout.compute_readout()
    assert r["schema_version"] == "crystal-atlas.catalog.ops.readout.v0"
    assert r["window"]["events_scanned"] == 0
    assert r["resolve"] == {"total": 0, "hits": 0, "misses": 0, "hit_rate": None, "by_kind": {}}
    assert r["hot_entries"] == [] and r["top_misses"] == []
    assert r["dcat"]["coverage_of_resolved_assets"] is None
    assert r["sources"]["cataloged"] == 0 and r["sources"]["cold"] == []


def test_resolve_hit_miss_and_rate(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    r = readout.compute_readout()
    # 2 asset hits + 1 source hit = 3 hits; 3 ghost misses; total 6; rate 0.5
    assert r["resolve"]["hits"] == 3
    assert r["resolve"]["misses"] == 3
    assert r["resolve"]["total"] == 6
    assert r["resolve"]["hit_rate"] == 0.5
    assert r["resolve"]["by_kind"]["asset"] == {"total": 5, "hits": 2, "misses": 3}
    assert r["resolve"]["by_kind"]["source"] == {"total": 1, "hits": 1, "misses": 0}


def test_hot_entries_and_top_misses_ranking(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    r = readout.compute_readout()
    hot = r["hot_entries"]
    # asset/asset-ro-1 (3 resolves: 2 hit + ... no, ghost is separate) — asset-ro-1
    # has 2 resolves, ghost has 3, src-1 has 1. ghost is hottest by resolve count.
    assert hot[0] == {"kind": "asset", "entry_id": "ghost", "resolves": 3}
    assert {"kind": "asset", "entry_id": "asset-ro-1", "resolves": 2} in hot
    # top misses = registration candidates: only ghost missed (3x)
    assert r["top_misses"] == [{"kind": "asset", "entry_id": "ghost", "misses": 3}]


def test_dcat_coverage(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    r = readout.compute_readout()
    # 1 DCAT emission for asset-ro-1, which was also HIT → coverage 1/1 = 1.0
    assert r["dcat"]["emissions"] == 1
    assert r["dcat"]["distinct_assets"] == 1
    assert r["dcat"]["coverage_of_resolved_assets"] == 1.0


def test_cold_sources(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    r = readout.compute_readout()
    # 2 cataloged sources; src-1 was read, src-cold never → cold = [src-cold]
    assert r["sources"]["cataloged"] == 2
    assert r["sources"]["read_in_window"] == 1
    assert r["sources"]["cold"] == ["src-cold"]


def test_emit_crystallizes_a_readout_event(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    doc, event_id = readout.emit_readout()
    assert event_id is not None
    ev_dir = tmp_path / "prophet-platform" / "events" / "catalog-gateway"
    written = [json.loads(p.read_text()) for p in ev_dir.glob("*.event.json")]
    readouts = [e for e in written if e["event_type"] == "crystal-atlas.catalog.ops.readout.v0"]
    assert len(readouts) == 1
    assert readouts[0]["event"]["readout_id"] == doc["readout_id"]
    # the crystallized readout does not count itself as a resolve/dcat KPI
    assert readouts[0]["event"]["resolve"]["total"] == 6


def test_readout_is_deterministic_for_fixed_events(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    from app import readout
    a = readout.compute_readout()
    b = readout.compute_readout()
    # KPIs identical run-to-run; only the id + generated_at differ.
    for key in ("resolve", "hot_entries", "top_misses", "dcat", "sources"):
        assert a[key] == b[key]


def test_route_get_and_post(monkeypatch, tmp_path):
    _drive(monkeypatch, tmp_path)
    g = client.get("/v1/catalog/ops/readout")
    assert g.status_code == 200
    assert g.json()["resolve"]["total"] == 6
    p = client.post("/v1/catalog/ops/readout")
    assert p.status_code == 200
    body = p.json()
    assert body["event_id"] is not None
    assert body["readout"]["resolve"]["hits"] == 3
    # the GET route must not be shadowed by the generic /{kind}/{entry_id} resolver
    assert "ops" not in [h["kind"] for h in g.json()["hot_entries"]]
