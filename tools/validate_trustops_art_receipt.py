#!/usr/bin/env python3
"""Validate synthetic TrustOps ART-smoke receipts emitted by prophet-platform."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED = {
    "schemaVersion",
    "receiptId",
    "receiptType",
    "subject",
    "runner",
    "inputs",
    "evaluation",
    "policy",
    "result",
    "evidence",
    "actions",
    "provenance",
}
POLICY_DECISIONS = {"allow", "warn", "require-review", "quarantine", "block", "rollback", "revoke"}
RESULT_STATUS = {"pass", "warn", "fail", "error"}
METRIC_STATUS = {"pass", "warn", "fail", "info"}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"{path}: expected JSON object")
    return payload


def require_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        fail(f"{key}: expected non-empty string")
    return value


def require_list(record: dict[str, Any], key: str, *, allow_empty: bool = False) -> list[Any]:
    value = record.get(key)
    if not isinstance(value, list):
        fail(f"{key}: expected list")
    if not allow_empty and not value:
        fail(f"{key}: expected non-empty list")
    return value


def validate_receipt(record: dict[str, Any]) -> None:
    missing = sorted(REQUIRED - set(record))
    if missing:
        fail(f"missing required fields: {missing}")
    if record["schemaVersion"] != "trustops-receipt.v1":
        fail("schemaVersion mismatch")
    if not require_string(record, "receiptId").startswith("trustops."):
        fail("receiptId must be trustops.*")
    if record["receiptType"] != "robustness":
        fail("synthetic art-smoke receiptType must be robustness")
    validate_subject(record.get("subject"))
    validate_runner(record.get("runner"))
    validate_inputs(record.get("inputs"))
    validate_evaluation(record.get("evaluation"))
    validate_policy(record.get("policy"))
    validate_result(record.get("result"))
    validate_evidence(record.get("evidence"))
    validate_actions(record.get("actions"))
    validate_provenance(record.get("provenance"))


def validate_subject(value: Any) -> None:
    if not isinstance(value, dict):
        fail("subject must be an object")
    for key in ("kind", "id", "ownerRepository", "versionRef"):
        require_string(value, key)
    if value["kind"] != "functional-service":
        fail("synthetic art-smoke subject.kind must be functional-service")
    if value["ownerRepository"] != "SocioProphet/prophet-platform":
        fail("subject.ownerRepository must remain prophet-platform for this slice")


def validate_runner(value: Any) -> None:
    if not isinstance(value, dict):
        fail("runner must be an object")
    for key in ("id", "provider", "version", "executionMode"):
        require_string(value, key)
    if value["id"] != "trustops-art-runner/art-smoke":
        fail("runner.id mismatch")
    if value["provider"] != "art":
        fail("runner.provider must identify ART as backend surface")
    if value["executionMode"] != "ci":
        fail("synthetic runner executionMode must be ci")


def validate_inputs(value: Any) -> None:
    if not isinstance(value, dict):
        fail("inputs must be an object")
    require_list(value, "manifests")
    if value.get("dataBoundary") != "synthetic":
        fail("first art-smoke runner slice must use synthetic dataBoundary")
    if value.get("rawDataExported") is not False:
        fail("rawDataExported must be false")


def validate_evaluation(value: Any) -> None:
    if not isinstance(value, dict):
        fail("evaluation must be an object")
    if value.get("profile") != "art-smoke":
        fail("evaluation.profile must be art-smoke")
    metrics = require_list(value, "metrics")
    for metric in metrics:
        if not isinstance(metric, dict):
            fail("metrics entries must be objects")
        for key in ("name", "value", "threshold", "status"):
            if key not in metric:
                fail(f"metric missing {key}")
        if metric["status"] not in METRIC_STATUS:
            fail(f"unknown metric status: {metric['status']}")


def validate_policy(value: Any) -> None:
    if not isinstance(value, dict):
        fail("policy must be an object")
    require_string(value, "gateRef")
    decision = require_string(value, "decision")
    if decision not in POLICY_DECISIONS:
        fail(f"unknown policy decision: {decision}")


def validate_result(value: Any) -> None:
    if not isinstance(value, dict):
        fail("result must be an object")
    status = require_string(value, "status")
    if status not in RESULT_STATUS:
        fail(f"unknown result status: {status}")
    require_string(value, "summary")


def validate_evidence(value: Any) -> None:
    if not isinstance(value, dict):
        fail("evidence must be an object")
    refs = require_list(value, "artifactRefs")
    if any(not isinstance(ref, str) or not ref.startswith("evidence://") for ref in refs):
        fail("artifactRefs must be redacted evidence:// refs")
    if value.get("redactionPolicy") != "metrics-only":
        fail("synthetic art-smoke evidence must use metrics-only redaction")


def validate_actions(value: Any) -> None:
    if not isinstance(value, list) or not value:
        fail("actions must be a non-empty list")
    targets = {item.get("target") for item in value if isinstance(item, dict)}
    if "model-governance-ledger" not in targets:
        fail("actions must include model-governance-ledger record action")
    if "guardrail-fabric" not in targets:
        fail("actions must include guardrail-fabric downstream action")


def validate_provenance(value: Any) -> None:
    if not isinstance(value, dict):
        fail("provenance must be an object")
    for key in ("createdAt", "createdBy", "sourceCommit", "receiptDigest"):
        require_string(value, key)
    if value["createdBy"] != "SocioProphet/prophet-platform/apps/trustops-art-runner":
        fail("createdBy must identify the platform runner")
    if not value["receiptDigest"].startswith("sha256:"):
        fail("receiptDigest must be sha256-bound")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_trustops_art_receipt.py <receipt.json>", file=sys.stderr)
        return 2
    try:
        validate_receipt(load_json(Path(argv[1])))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {argv[1]} validates as synthetic TrustOps ART-smoke receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
