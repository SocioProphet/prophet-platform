from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


execute_bound_main = _load_module("workflow_local_runner_execute_bound_main", ROOT / "app" / "execute_bound_main.py")

client = TestClient(execute_bound_main.app)


def test_execute_bound_api_emits_bound_bundle(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))

    body = {
        "service": "workflow-local-runner",
        "correlation_id": "corr-exec-bound-001",
        "workflow_run": {
            "runId": "run-exec-bound-001",
            "workflowRef": "workflow://agentic-workbench/demo-exec-bound",
            "workflowDigest": "sha256:0fe7287e778d169f7a301e9fdb5e356af77326da64c109134c673e7de3c68047",
            "createdAt": "2026-04-16T06:30:00Z",
            "status": "pending",
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09"
        },
        "execution_envelope": {
            "envelopeId": "env-exec-bound-001",
            "runId": "run-exec-bound-001",
            "stepId": "step-exec-bound-001",
            "subject": {
                "spiffeId": "spiffe://sourceos.local/workbench/tester",
                "aumDigest": "sha256:291fe26bea42f33f894c074b90e5d4d14b5242fda4d083ff1c06251bcde9b788"
            },
            "inputDigest": "sha256:a9d7323b6b1d8e69a42f27cbcf23ba29e59760edc39dbcd96bd476201c96ab09",
            "policyDecisionRef": "policy-decision://exec-bound-001"
        },
        "payload": {
            "message": "execute and materialize bound bundle"
        }
    }

    resp = client.post("/v1/runs/local-execute-bound", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["correlation_id"] == "corr-exec-bound-001"
    assert payload["bound_bundle_ref"].startswith("file://")

    bundle_path = tmp_path / "prophet-platform" / "bundles" / "workflow-local-runner" / "corr-exec-bound-001.bound_bundle.json"
    assert bundle_path.exists()
    rendered = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert rendered["runBundle"]["run"]["runId"] == "run-exec-bound-001"
    assert rendered["maipjRunReceipt"]["status"] == "succeeded"
