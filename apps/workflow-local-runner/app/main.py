from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Prophet Platform Workflow Local Runner", version="0.1.0")


SERVICE_NAME = "workflow-local-runner"
EVENT_TYPE = "workflow.local.execution.v0"
ACTION = "LocalWorkflowRun"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def _platform_root() -> Path:
    return _state_home() / "prophet-platform"


def _ensure_dirs(service: str) -> dict[str, Path]:
    root = _platform_root()
    payload_dir = root / "payloads" / service
    event_dir = root / "events" / service
    receipt_dir = root / "receipts" / service
    catalog_dir = root / "catalog" / service
    for path in [payload_dir, event_dir, receipt_dir, catalog_dir]:
        path.mkdir(parents=True, exist_ok=True)
    return {
        "payload_dir": payload_dir,
        "event_dir": event_dir,
        "receipt_dir": receipt_dir,
        "catalog_file": catalog_dir / "receipt_catalog.jsonl",
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/v1/runs/local-execute")
def local_execute(body: dict[str, Any]) -> dict[str, Any]:
    workflow_run = body.get("workflow_run")
    execution_envelope = body.get("execution_envelope")
    payload = body.get("payload", {})
    service = body.get("service", SERVICE_NAME)

    if not isinstance(workflow_run, dict) or not workflow_run:
        raise HTTPException(status_code=400, detail="workflow_run is required and must be an object")
    if not isinstance(execution_envelope, dict) or not execution_envelope:
        raise HTTPException(status_code=400, detail="execution_envelope is required and must be an object")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object when provided")

    correlation_id = body.get("correlation_id") or str(uuid.uuid4())
    created_at = _utcnow()
    dirs = _ensure_dirs(service)

    workflow_run_digest = _stable_digest(workflow_run)
    execution_envelope_digest = _stable_digest(execution_envelope)
    payload_digest = _stable_digest(payload)

    run_id = (
        workflow_run.get("run_id")
        or workflow_run.get("id")
        or workflow_run.get("workflow_run_id")
        or correlation_id
    )
    subject_ref = f"workflow-run://{run_id}"

    payload_doc = {
        "service": service,
        "correlation_id": correlation_id,
        "created_at": created_at,
        "workflow_run": workflow_run,
        "execution_envelope": execution_envelope,
        "payload": payload,
        "digests": {
            "workflow_run_sha256": workflow_run_digest,
            "execution_envelope_sha256": execution_envelope_digest,
            "payload_sha256": payload_digest,
        },
    }

    payload_path = dirs["payload_dir"] / f"{correlation_id}.payload.json"
    payload_path.write_text(json.dumps(payload_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    event_doc = {
        "event_type": EVENT_TYPE,
        "service": service,
        "correlation_id": correlation_id,
        "created_at": created_at,
        "subject_ref": subject_ref,
        "payload_ref": f"file://{payload_path.resolve()}",
        "execution_record": {
            "phase": "result",
            "status": "succeeded",
            "artifact_refs": [f"file://{payload_path.resolve()}"],
            "workflow_run_digest": workflow_run_digest,
            "execution_envelope_digest": execution_envelope_digest,
            "payload_digest": payload_digest,
        },
    }

    event_path = dirs["event_dir"] / f"{correlation_id}.event.json"
    event_path.write_text(json.dumps(event_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt_doc = {
        "status": "succeeded",
        "action": ACTION,
        "service": service,
        "created_at": created_at,
        "correlation_id": correlation_id,
        "subject_ref": subject_ref,
        "source_binding": {
            "workflow_run": "sociosphere.WorkflowRun",
            "execution_envelope": "sociosphere.ExecutionEnvelope",
            "normalized_receipt": "standards-storage.maipj-run-receipt",
        },
        "run_identity": {
            "run_id": run_id,
            "workflow_run_sha256": workflow_run_digest,
            "execution_envelope_sha256": execution_envelope_digest,
            "payload_sha256": payload_digest,
        },
        "evidence": {
            "event_ref": f"file://{event_path.resolve()}",
            "payload_ref": f"file://{payload_path.resolve()}",
        },
        "outcome": {
            "result": "success",
            "local_runner": True,
        },
    }

    receipt_path = dirs["receipt_dir"] / f"{correlation_id}.receipt.json"
    receipt_path.write_text(json.dumps(receipt_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    catalog_entry = {
        "service": service,
        "correlation_id": correlation_id,
        "created_at": created_at,
        "event_type": EVENT_TYPE,
        "subject_ref": subject_ref,
        "payload_ref": f"file://{payload_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}",
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "classifiers": ["workflow-run", "local-runner", "receipt-backed"],
    }
    with dirs["catalog_file"].open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(catalog_entry, sort_keys=True) + "\n")

    return {
        "service": service,
        "correlation_id": correlation_id,
        "subject_ref": subject_ref,
        "payload_ref": f"file://{payload_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}",
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "catalog_ref": f"file://{dirs['catalog_file'].resolve()}",
        "digests": payload_doc["digests"],
    }
