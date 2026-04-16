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
materializer = _load_module("workflow_local_runner_materializer", ROOT / "app" / "materialize_bound_bundle.py")
evidence_store = _load_module(
    "evidence_receipts_store",
    PLATFORM_ROOT / "evidence-receipts" / "app" / "store.py",
)

local_client = TestClient(local_main.app)


def test_materialize_bound_bundle_writes_bundle_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    body = {
        "service": "workflow-local-runner",
        "correlation_id": "corr-materialize-001",
        "workflow_run": {
            "runId": "run-materialize-001",
            "workflowRef": "workflow://agentic-workbench/demo-materialize",
            "workflowDigest": "sha256:0fe7287e778d169f7a301e9fdb5e356af77326da64c109134c673e7de3c68047",
            "createdAt": "2026-04-16T06:10:00Z",
            "status": "pending",
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09"
        },
        "execution_envelope": {
            "envelopeId": "env-materialize-001",
            "runId": "run-materialize-001",
            "stepId": "step-materialize-001",
            "subject": {
                "spiffeId": "spiffe://sourceos.local/workbench/tester",
                "aumDigest": "sha256:291fe26bea42f33f894c074b90e5d4d14b5242fda4d083ff1c06251bcde9b788"
            },
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09",
            "policyDecisionRef": "policy-decision://materialize-001"
        },
        "payload": {
            "message": "materialize bound bundle"
        }
    }

    execute = local_client.post("/v1/runs/local-execute", json=body)
    assert execute.status_code == 200

    bundle = evidence_store.get_bundle(service="workflow-local-runner", correlation_id="corr-materialize-001")
    assert bundle is not None

    out_path = materializer.materialize_bound_bundle(
        service="workflow-local-runner",
        correlation_id="corr-materialize-001",
        workflow_run=bundle["payload"]["workflow_run"],
        execution_envelope=bundle["payload"]["execution_envelope"],
        event_doc=bundle["event"],
        receipt_doc=bundle["receipt"],
        payload_doc=bundle["payload"],
        catalog_entry=bundle["catalog_entry"],
        platform_root=tmp_path / "prophet-platform",
    )

    assert out_path.exists()
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["runBundle"]["run"]["runId"] == "run-materialize-001"
    assert rendered["maipjRunReceipt"]["placement"]["mode"] == "local"
    assert rendered["publicationReceipt"]["status"] == "succeeded"
