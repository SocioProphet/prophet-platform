from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "workflow-local-runner"


def test_local_execute_writes_receipt_bundle(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    body = {
        "service": "workflow-local-runner",
        "correlation_id": "corr-workflow-001",
        "workflow_run": {
            "run_id": "run-001",
            "workflow_ref": "workflow://demo",
            "caller_ref": "principal://tester",
        },
        "execution_envelope": {
            "subject_ref": "workflow-run://run-001",
            "policy_ref": "policy://demo",
        },
        "payload": {
            "message": "hello local runner"
        },
    }

    resp = client.post("/v1/runs/local-execute", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["correlation_id"] == "corr-workflow-001"
    assert data["subject_ref"] == "workflow-run://run-001"

    root = tmp_path / "prophet-platform"
    payload_path = root / "payloads" / "workflow-local-runner" / "corr-workflow-001.payload.json"
    event_path = root / "events" / "workflow-local-runner" / "corr-workflow-001.event.json"
    receipt_path = root / "receipts" / "workflow-local-runner" / "corr-workflow-001.receipt.json"
    catalog_path = root / "catalog" / "workflow-local-runner" / "receipt_catalog.jsonl"

    assert payload_path.exists()
    assert event_path.exists()
    assert receipt_path.exists()
    assert catalog_path.exists()

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    event = json.loads(event_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    catalog_lines = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert payload["workflow_run"]["run_id"] == "run-001"
    assert event["event_type"] == "workflow.local.execution.v0"
    assert receipt["source_binding"]["workflow_run"] == "sociosphere.WorkflowRun"
    assert catalog_lines[-1]["correlation_id"] == "corr-workflow-001"
