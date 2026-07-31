"""Catalog Gateway tests — resolve, lineage, DCAT emitter, path-traversal guard."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app import store  # noqa: E402

client = TestClient(app)

ASSET = {
    "asset_id": "asset-demo-001",
    "asset_kind": "dataset",
    "tenant_id": "tenant-a",
    "distribution_class": "public_derived",
    "source_refs": ["src-gov-001"],
    "schema_ref": "contracts/crystal-atlas/schemas/asset-catalog-entry.v0.schema.json",
    "freshness": {"cadence": "daily"},
    "created_at": "2026-07-31T00:00:00Z",
    "updated_at": "2026-07-31T00:00:00Z",
}


def _seed(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    d = tmp_path / "prophet-platform" / "catalog" / "asset"
    d.mkdir(parents=True, exist_ok=True)
    (d / "asset-demo-001.json").write_text(json.dumps(ASSET), encoding="utf-8")


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["service"] == "catalog-gateway"


def test_resolve_found(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    r = client.get("/v1/catalog/asset/asset-demo-001")
    assert r.status_code == 200
    assert r.json()["entry"]["tenant_id"] == "tenant-a"


def test_resolve_missing_is_404(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/asset/nope").status_code == 404


def test_unknown_kind_is_404(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    assert client.get("/v1/catalog/bogus/asset-demo-001").status_code == 404


def test_dcat_emitter(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    r = client.get("/v1/catalog/asset/asset-demo-001.dcat.json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/ld+json")
    doc = r.json()
    assert "dcat:Dataset" in doc["@type"]
    assert doc["dct:accessRights"] == "public"          # public_derived → public
    assert doc["dct:identifier"] == "asset-demo-001"
    assert doc["prov:wasDerivedFrom"] == [{"@id": "src-gov-001"}]
    assert doc["prophet:distributionClass"] == "public_derived"   # the moat, exported
    assert doc["@context"]["dcat"].startswith("http://www.w3.org/ns/dcat")


def test_lineage(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    r = client.get("/v1/catalog/asset/asset-demo-001/lineage")
    assert r.status_code == 200
    up = r.json()["upstream"]
    assert up and up[0]["ref"] == "src-gov-001"


def test_id_validation_and_traversal_guard():
    assert store.is_valid_id("asset-demo-001")
    for bad in ("../etc/passwd", "a/b", "..", "a\x00b", ""):
        assert not store.is_valid_id(bad)
    # get_entry fails closed on a traversal id
    assert store.get_entry("asset", "../../secret") is None
