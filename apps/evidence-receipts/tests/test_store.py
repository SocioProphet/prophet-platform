from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.store as store  # type: ignore


def test_resolve_layout_service_first(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    root = tmp_path / "prophet-platform" / "eval-fabric-api" / "receipts"
    root.mkdir(parents=True)
    layout = store.resolve_layout("eval-fabric-api")
    assert layout.receipt_dir == root


def test_resolve_layout_type_first(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    root = tmp_path / "prophet-platform" / "receipts" / "lampstand"
    root.mkdir(parents=True)
    layout = store.resolve_layout("lampstand")
    assert layout.receipt_dir == root


def test_lampstand_bundle_uses_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    base = tmp_path / "prophet-platform"
    (base / "payloads" / "lampstand").mkdir(parents=True, exist_ok=True)
    (base / "events" / "lampstand").mkdir(parents=True, exist_ok=True)
    (base / "receipts" / "lampstand").mkdir(parents=True, exist_ok=True)
    (base / "catalog" / "lampstand").mkdir(parents=True, exist_ok=True)

    corr = "lamp-123"
    payload_path = base / "payloads" / "lampstand" / f"{corr}.CarrierIngested.json"
    event_path = base / "events" / "lampstand" / f"{corr}.event.json"
    receipt_path = base / "receipts" / "lampstand" / f"{corr}.receipt.json"

    payload_path.write_text(json.dumps({"carrier_ref": "carrier://sha256/abc"}) + "\n", encoding="utf-8")
    event_path.write_text(json.dumps({"event_type": "carrier.ingested", "created_at": "2026-04-09T00:00:00+00:00"}) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps({"status": "succeeded", "action": "CarrierIngest", "subject_ref": "carrier://sha256/abc"}) + "\n", encoding="utf-8")
    catalog = base / "catalog" / "lampstand" / "receipt_catalog.jsonl"
    catalog.write_text(json.dumps({
        "correlation_id": corr,
        "payload_ref": f"file://{payload_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}",
        "receipt_ref": f"file://{receipt_path.resolve()}",
    }) + "\n", encoding="utf-8")

    bundle = store.get_bundle(service="lampstand", correlation_id=corr)
    assert bundle is not None
    assert bundle["payload"]["carrier_ref"] == "carrier://sha256/abc"
    recent = store.list_recent_bundles(service="lampstand", limit=5)
    assert recent[0]["correlation_id"] == corr


def test_list_services_detects_both_layouts(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    (tmp_path / "prophet-platform" / "eval-fabric-api" / "receipts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "prophet-platform" / "receipts" / "lampstand").mkdir(parents=True, exist_ok=True)
    services = store.list_services()
    assert "eval-fabric-api" in services
    assert "lampstand" in services
