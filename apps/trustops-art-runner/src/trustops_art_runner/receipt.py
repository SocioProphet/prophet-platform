"""Receipt builder for the TrustOps ART runner.

The first implementation is deliberately deterministic and synthetic. It proves the
Prophet Platform TrustOps control-plane seam before importing ART or other heavy
provider dependencies into an isolated runner image.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


TRUSTOPS_SCHEMA_VERSION = "trustops-receipt.v1"
DEFAULT_RUNNER_ID = "trustops-art-runner"
DEFAULT_PROVIDER_VERSION = "synthetic-art-smoke-0.1.0"
ZERO_COMMIT = "0000000000000000000000000000000000000000"


class TrustOpsRunnerError(ValueError):
    """Raised when runner input cannot produce a valid receipt."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - stdlib message is enough
        raise TrustOpsRunnerError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TrustOpsRunnerError(f"expected object JSON in {path}")
    return data


def _service_subject(manifest: dict[str, Any]) -> dict[str, str]:
    service = manifest.get("service")
    if not isinstance(service, dict):
        raise TrustOpsRunnerError("manifest.service is required")

    service_id = service.get("id")
    owner_repository = service.get("ownerRepository")
    if not isinstance(service_id, str) or not service_id:
        raise TrustOpsRunnerError("manifest.service.id is required")
    if not isinstance(owner_repository, str) or "/" not in owner_repository:
        raise TrustOpsRunnerError("manifest.service.ownerRepository must be owner/name")

    model = manifest.get("model", {})
    model_ref = model.get("modelRef") if isinstance(model, dict) else None
    version_ref = model_ref if isinstance(model_ref, str) and model_ref else "manifest-local"

    return {
        "kind": "functional-service",
        "id": service_id,
        "ownerRepository": owner_repository,
        "versionRef": version_ref,
        "functionalServiceRef": f"functional-service.{service_id}",
    }


def _digest_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_art_smoke_receipt(
    *,
    manifest_path: Path,
    profile: str = "art-smoke",
    output_ref: str | None = None,
    source_commit: str = ZERO_COMMIT,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic TrustOps robustness receipt.

    The synthetic backend intentionally emits stable metrics below blocking
    thresholds. Later ART-backed probes must preserve this external contract.
    """

    if profile != "art-smoke":
        raise TrustOpsRunnerError(f"unsupported profile: {profile}")

    manifest = _load_json(manifest_path)
    subject = _service_subject(manifest)
    timestamp = created_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    model_ref = subject["versionRef"]
    receipt_id = f"trustops.art-smoke.{subject['id']}.{hashlib.sha1(str(manifest_path).encode('utf-8')).hexdigest()[:8]}"

    receipt: dict[str, Any] = {
        "schemaVersion": TRUSTOPS_SCHEMA_VERSION,
        "receiptId": receipt_id,
        "receiptType": "robustness",
        "subject": subject,
        "runner": {
            "id": DEFAULT_RUNNER_ID,
            "provider": "art",
            "version": DEFAULT_PROVIDER_VERSION,
            "executionMode": "ci",
            "containerRef": "ghcr.io/socioprophet/trustops-art-runner:0.1.0",
            "codeDigest": "sha256:synthetic-art-smoke",
        },
        "inputs": {
            "manifests": [str(manifest_path)],
            "datasetRefs": ["dataset-risk.synthetic-art-smoke"],
            "modelRefs": [model_ref],
            "policyRefs": ["trustgate.platform-default"],
            "protectedAttributeRefs": [],
            "dataBoundary": "synthetic",
            "rawDataExported": False,
        },
        "evaluation": {
            "profile": profile,
            "threatClasses": ["evasion", "inference", "extraction"],
            "metricFamilies": ["robustness", "privacy-leakage"],
            "metrics": [
                {
                    "name": "evasion_attack_success_rate",
                    "value": 0.08,
                    "threshold": 0.10,
                    "direction": "at-or-below",
                    "status": "pass",
                    "sliceRef": "all",
                },
                {
                    "name": "membership_inference_risk",
                    "value": "low",
                    "threshold": "medium",
                    "direction": "at-or-below",
                    "status": "pass",
                    "sliceRef": "all",
                },
                {
                    "name": "model_extraction_probe",
                    "value": "not-detected",
                    "threshold": "detected",
                    "direction": "equals",
                    "status": "pass",
                    "sliceRef": "all",
                },
            ],
        },
        "policy": {
            "gateRef": "trustgate.platform-default.robustness",
            "decision": "allow",
            "reviewer": "automation",
        },
        "result": {
            "status": "pass",
            "summary": "Synthetic ART smoke profile passed. This receipt validates the TrustOps runner seam before full ART-backed adversarial probes are enabled.",
            "residualRisk": "low",
            "recommendedMitigations": [
                "Run full ART-backed robustness profile before production promotion.",
                "Record the receipt in model-governance-ledger before enabling runtime promotion.",
            ],
        },
        "evidence": {
            "artifactRefs": [output_ref or "artifact://trustops/art-smoke/receipt.json"],
            "redactionPolicy": "metrics-only",
            "factsheetRefs": [f"factsheet.{subject['id']}"],
        },
        "actions": [
            {
                "target": "model-governance-ledger",
                "action": "record",
                "details": "Store robustness receipt and promotion evidence.",
            },
            {
                "target": "guardrail-fabric",
                "action": "allow",
                "details": "Synthetic smoke profile produced no blocking robustness signal.",
            },
        ],
        "provenance": {
            "createdAt": timestamp,
            "createdBy": DEFAULT_RUNNER_ID,
            "sourceCommit": source_commit,
            "receiptDigest": "sha256:pending",
            "signatureRef": "unsigned://local-smoke",
        },
    }
    receipt["provenance"]["receiptDigest"] = _digest_json({k: v for k, v in receipt.items() if k != "provenance"})
    return receipt


def write_receipt(receipt: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = ["TrustOpsRunnerError", "build_art_smoke_receipt", "write_receipt"]
