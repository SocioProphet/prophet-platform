from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = ROOT.parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local_main = _load_module("workflow_local_runner_main", ROOT / "app" / "main.py")
bound_bundle = _load_module("workflow_local_runner_bound_bundle", ROOT / "app" / "bound_bundle.py")
evidence_main = _load_module(
    "evidence_receipts_main",
    PLATFORM_ROOT / "evidence-receipts" / "app" / "main.py",
)

local_client = TestClient(local_main.app)
evidence_client = TestClient(evidence_main.app)


def test_local_run_visible_in_evidence_receipts_and_bound_bundle(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    body = {
        "service": "workflow-local-runner",
        "correlation_id": "corr-bound-001",
        "workflow_run": {
            "runId": "run-bound-001",
            "workflowRef": "workflow://agentic-workbench/demo-bound-run",
            "workflowDigest": "sha256:0fe7287e778d169f7a301e9fdb5e356af77326da64c109134c673e7de3c68047",
            "createdAt": "2026-04-16T06:00:00Z",
            "status": "pending",
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09",
        },
        "execution_envelope": {
            "envelopeId": "env-bound-001",
            "runId": "run-bound-001",
            "stepId": "step-bound-001",
            "subject": {
                "spiffeId": "spiffe://sourceos.local/workbench/tester",
                "aumDigest": "sha256:291fe26bea42f33f894c074b90e5d4d14b5242fda4d083ff1c06251bcde9b788",
            },
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09",
            "policyDecisionRef": "policy-decision://bound-001",
        },
        "payload": {
            "message": "bound bundle demo"
        },
    }

    execute = local_client.post("/v1/runs/local-execute", json=body)
    assert execute.status_code == 200
    execute_json = execute.json()
    correlation_id = execute_json["correlation_id"]

    recent = evidence_client.get(
        "/v1/receipts/recent",
        params={"service": "workflow-local-runner", "limit": 5},
    )
    assert recent.status_code == 200
    recent_items = recent.json()["items"]
    assert len(recent_items) == 1
    assert recent_items[0]["correlation_id"] == correlation_id

    detail = evidence_client.get(f"/v1/receipts/workflow-local-runner/{correlation_id}")
    assert detail.status_code == 200
    bundle = detail.json()
    assert bundle["receipt"]["status"] == "succeeded"
    assert bundle["event"]["event_type"] == "workflow.local.execution.v0"

    projected = bound_bundle.build_bound_bundle(
        workflow_run=bundle["payload"]["workflow_run"],
        execution_envelope=bundle["payload"]["execution_envelope"],
        event_doc=bundle["event"],
        receipt_doc=bundle["receipt"],
        payload_doc=bundle["payload"],
        catalog_entry=bundle["catalog_entry"],
    )

    assert projected["runBundle"]["run"]["runId"] == "run-bound-001"
    assert projected["maipjRunReceipt"]["placement"]["mode"] == "local"
    assert projected["publicationReceipt"]["status"] == "succeeded"
