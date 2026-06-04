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


def test_resolve_layout_prefers_type_first_when_both_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    (tmp_path / "prophet-platform" / "eval-fabric-api" / "receipts").mkdir(parents=True)
    type_first = tmp_path / "prophet-platform" / "receipts" / "eval-fabric-api"
    type_first.mkdir(parents=True)
    layout = store.resolve_layout("eval-fabric-api")
    assert layout.receipt_dir == type_first


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


def test_eval_fabric_legacy_service_first_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    base = tmp_path / "prophet-platform" / "eval-fabric-api"
    (base / "payloads").mkdir(parents=True, exist_ok=True)
    (base / "events").mkdir(parents=True, exist_ok=True)
    (base / "receipts").mkdir(parents=True, exist_ok=True)

    corr = "legacy-ef-1"
    payload_path = base / "payloads" / f"{corr}.payload.json"
    event_path = base / "events" / f"{corr}.event.json"
    receipt_path = base / "receipts" / f"{corr}.receipt.json"
    payload_path.write_text(json.dumps({"profile_id": "profile.high_assurance_enterprise_agent"}) + "\n", encoding="utf-8")
    event_path.write_text(json.dumps({"event_type": "eval.fabric.frontier.read", "payload_ref": f"file://{payload_path.resolve()}"}) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps({"status": "succeeded", "action": "FrontierQuery"}) + "\n", encoding="utf-8")

    bundle = store.get_bundle(service="eval-fabric-api", correlation_id=corr)
    assert bundle is not None
    assert bundle["payload"]["profile_id"] == "profile.high_assurance_enterprise_agent"


def test_policy_simulation_evidence_bundle_type_first(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    base = tmp_path / "prophet-platform"
    service = "policy-simulation"
    (base / "payloads" / service).mkdir(parents=True, exist_ok=True)
    (base / "events" / service).mkdir(parents=True, exist_ok=True)
    (base / "receipts" / service).mkdir(parents=True, exist_ok=True)

    corr = "policy-sim-source-intake-run-001"
    subject_ref = "policy-simulation-measured:policy-sim-source-intake-001"
    payload_path = base / "payloads" / service / f"{corr}.payload.json"
    event_path = base / "events" / service / f"{corr}.event.json"
    receipt_path = base / "receipts" / service / f"{corr}.receipt.json"

    payload_path.write_text(json.dumps({
        "measured_entity_id": subject_ref,
        "advisory_status": "advisory_evidence_only",
        "governance_control": {
            "runtime_dependency": False,
            "release_authority": "advisory_only",
            "live_policy_automation": False,
            "value_release_authorized": False,
        },
        "triparty_measurement": {
            "lambda_evid": 1.0,
            "lambda_admit": 0.8,
            "lambda_release": 0.6,
            "residual": 0.4,
            "release_ratio": 0.6,
            "residual_ratio": 0.4,
            "state": "ReviewRequired",
        },
    }) + "\n", encoding="utf-8")
    event_path.write_text(json.dumps({
        "event_type": "policy_simulation.evidence.accepted_for_review",
        "created_at": "2026-06-04T07:16:23Z",
        "subject_ref": subject_ref,
        "payload_ref": f"file://{payload_path.resolve()}",
    }) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps({
        "status": "accepted_for_review",
        "action": "PolicySimulationEvidenceReview",
        "subject_ref": subject_ref,
    }) + "\n", encoding="utf-8")

    bundle = store.get_bundle(service=service, correlation_id=corr)
    assert bundle is not None
    assert bundle["payload"]["measured_entity_id"] == subject_ref
    assert bundle["payload"]["governance_control"]["runtime_dependency"] is False
    assert bundle["payload"]["triparty_measurement"]["release_ratio"] == 0.6
    recent = store.list_recent_bundles(service=service, limit=5)
    assert recent[0]["status"] == "accepted_for_review"
    assert recent[0]["subject_ref"] == subject_ref
    assert service in store.list_services()


def test_list_services_detects_both_layouts(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    (tmp_path / "prophet-platform" / "eval-fabric-api" / "receipts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "prophet-platform" / "receipts" / "lampstand").mkdir(parents=True, exist_ok=True)
    services = store.list_services()
    assert "eval-fabric-api" in services
    assert "lampstand" in services
