from __future__ import annotations

from typing import Any


def build_bound_bundle(
    *,
    workflow_run: dict[str, Any],
    execution_envelope: dict[str, Any],
    event_doc: dict[str, Any],
    receipt_doc: dict[str, Any],
    payload_doc: dict[str, Any],
    catalog_entry: dict[str, Any],
) -> dict[str, Any]:
    """Project local runner state into the normalized bound bundle view described
    by workbench-run-bundle-receipt-binding-v0.1.

    This helper does not redefine upstream schema law. It produces an operator- and
    test-friendly projection over the current local-runner artifacts.
    """

    run_id = str(workflow_run.get("runId") or workflow_run.get("run_id") or workflow_run.get("id") or receipt_doc.get("correlation_id"))
    workflow_digest = str(workflow_run.get("workflowDigest") or payload_doc.get("digests", {}).get("workflow_run_sha256") or "")
    input_digest = str(workflow_run.get("inputDigest") or execution_envelope.get("inputDigest") or payload_doc.get("digests", {}).get("payload_sha256") or "")
    envelope_id = str(execution_envelope.get("envelopeId") or event_doc.get("correlation_id") or "")
    subject_ref = str(receipt_doc.get("subject_ref") or event_doc.get("subject_ref") or f"workflow-run://{run_id}")

    execution_record = {
        "recordId": event_doc.get("correlation_id"),
        "runId": run_id,
        "phase": event_doc.get("execution_record", {}).get("phase", "result"),
        "status": event_doc.get("execution_record", {}).get("status", receipt_doc.get("status")),
        "createdAt": event_doc.get("created_at") or receipt_doc.get("created_at"),
        "artifactRefs": [
            {
                "artifactId": f"artifact-payload-{event_doc.get('correlation_id')}",
                "kind": "output",
                "uri": event_doc.get("payload_ref"),
                "digest": payload_doc.get("digests", {}).get("payload_sha256", ""),
                "mediaType": "application/json",
            }
        ],
        "policyRef": execution_envelope.get("policyDecisionRef"),
        "signatureRef": None,
    }

    return {
        "bindingVersion": "v0.1",
        "canonicalSources": {
            "workflowRun": "sociosphere.WorkflowRun",
            "executionEnvelope": "sociosphere.ExecutionEnvelope",
            "executionRecord": "sociosphere.ExecutionRecord",
            "runBundle": "standards-storage.RunBundle",
            "normalizedReceipt": "standards-storage.maipj-run-receipt",
            "transportBinding": "TriTRPC.receipt_binding",
        },
        "workflowRun": workflow_run,
        "executionEnvelope": execution_envelope,
        "executionRecord": execution_record,
        "runBundle": {
            "bundleId": f"run-bundle-{event_doc.get('correlation_id')}",
            "run": {
                "runId": run_id,
                "workflowDigest": workflow_digest,
                "inputDigest": input_digest,
            },
            "execution": {
                "envelopeId": envelope_id,
                "subjectRef": subject_ref,
            },
            "records": [execution_record["recordId"]],
            "receiptRefs": [receipt_doc.get("receipt_ref")] if receipt_doc.get("receipt_ref") else [],
        },
        "maipjRunReceipt": {
            "receiptId": f"maipj-{event_doc.get('correlation_id')}",
            "status": receipt_doc.get("status"),
            "action": receipt_doc.get("action"),
            "subjectRef": subject_ref,
            "createdAt": receipt_doc.get("created_at"),
            "context": {
                "runId": run_id,
                "workflowRunSha256": payload_doc.get("digests", {}).get("workflow_run_sha256"),
                "executionEnvelopeSha256": payload_doc.get("digests", {}).get("execution_envelope_sha256"),
                "runtimeProfileRef": None,
            },
            "placement": {
                "mode": "local",
                "schedulerKind": "local",
            },
            "runtime": {
                "cpu": None,
                "memory": None,
                "gpu": 0,
            },
            "evidence": {
                "eventRef": receipt_doc.get("evidence", {}).get("event_ref"),
                "payloadRef": receipt_doc.get("evidence", {}).get("payload_ref"),
            },
            "outcome": {
                "result": receipt_doc.get("outcome", {}).get("result", receipt_doc.get("status")),
                "replayable": True,
            },
        },
        "publicationReceipt": {
            "receiptId": f"publication-{event_doc.get('correlation_id')}",
            "status": receipt_doc.get("status"),
            "subjectRef": subject_ref,
            "catalogRef": catalog_entry.get("receipt_ref"),
        },
    }
