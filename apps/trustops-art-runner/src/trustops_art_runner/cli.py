#!/usr/bin/env python3
"""Synthetic TrustOps ART-smoke receipt runner.

This runner intentionally does not import ART. It is the first functional
platform slice that emits a provider-neutral TrustOps receipt from synthetic
fixture inputs. Real ART integration can land later behind this receipt
boundary without changing downstream ledger/guardrail/registry semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "trustops-receipt.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def receipt_digest(receipt: dict[str, Any]) -> str:
    copy = dict(receipt)
    provenance = dict(copy.get("provenance", {}))
    provenance.pop("receiptDigest", None)
    copy["provenance"] = provenance
    encoded = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def decision_from_metrics(metrics: list[dict[str, Any]]) -> tuple[str, str, str]:
    statuses = {str(metric.get("status")) for metric in metrics}
    if "fail" in statuses:
        return "block", "fail", "Synthetic ART-smoke robustness check failed."
    if "warn" in statuses:
        return "warn", "warn", "Synthetic ART-smoke robustness check produced warnings."
    return "allow", "pass", "Synthetic ART-smoke robustness check passed."


def build_receipt(manifest: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    manifest_id = str(manifest.get("manifestId", "manifest:unknown"))
    subject = manifest.get("subject")
    if not isinstance(subject, dict):
        raise ValueError("manifest.subject must be an object")
    metrics = manifest.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("manifest.metrics must be a non-empty array")

    policy_decision, result_status, summary = decision_from_metrics(metrics)
    created_at = generated_at or utc_now()
    receipt: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "receiptId": str(manifest.get("receiptId", "trustops.art-smoke.synthetic-001")),
        "receiptType": "robustness",
        "subject": {
            "kind": str(subject.get("kind", "functional-service")),
            "id": str(subject.get("id", "unknown-subject")),
            "ownerRepository": str(subject.get("ownerRepository", "SocioProphet/prophet-platform")),
            "versionRef": str(subject.get("versionRef", "synthetic")),
            "functionalServiceRef": str(subject.get("functionalServiceRef", "functional-service://unknown")),
        },
        "runner": {
            "id": "trustops-art-runner/art-smoke",
            "provider": "art",
            "version": "0.1.0-synthetic",
            "executionMode": "ci",
            "containerRef": "container://not-required/synthetic-art-smoke",
            "codeDigest": str(manifest.get("runnerCodeDigest", "sha256:synthetic-runner")),
        },
        "inputs": {
            "manifests": [manifest_id],
            "datasetRefs": list(manifest.get("datasetRefs", ["dataset://synthetic/art-smoke"])),
            "modelRefs": list(manifest.get("modelRefs", [])),
            "policyRefs": list(manifest.get("policyRefs", ["policy://trustops/art-smoke-v0.1"])),
            "dataBoundary": str(manifest.get("dataBoundary", "synthetic")),
            "rawDataExported": False,
        },
        "evaluation": {
            "profile": "art-smoke",
            "threatClasses": ["evasion"],
            "metricFamilies": ["robustness"],
            "metrics": metrics,
        },
        "policy": {
            "gateRef": str(manifest.get("gateRef", "gate://trustops/art-smoke")),
            "decision": policy_decision,
        },
        "result": {
            "status": result_status,
            "summary": summary,
            "residualRisk": str(manifest.get("residualRisk", "low")),
            "recommendedMitigations": list(manifest.get("recommendedMitigations", [])),
        },
        "evidence": {
            "artifactRefs": list(manifest.get("evidenceArtifactRefs", ["evidence://trustops/art-smoke/metrics-001"])),
            "redactionPolicy": "metrics-only",
            "factsheetRefs": list(manifest.get("factsheetRefs", ["factsheet://trustops/art-smoke/synthetic-001"])),
        },
        "actions": [
            {"target": "model-governance-ledger", "action": "record", "details": "Record TrustOps receipt evidence only."},
            {"target": "guardrail-fabric", "action": policy_decision if policy_decision != "allow" else "allow", "details": "Downstream runtime-control decision remains separate."},
        ],
        "provenance": {
            "createdAt": created_at,
            "createdBy": "SocioProphet/prophet-platform/apps/trustops-art-runner",
            "sourceCommit": str(manifest.get("sourceCommit", "synthetic")),
            "receiptDigest": "sha256:pending",
        },
    }
    receipt["provenance"]["receiptDigest"] = receipt_digest(receipt)
    return receipt


def write_json(payload: dict[str, Any], output: str | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trustops-art-runner")
    parser.add_argument("run", choices=["run"])
    parser.add_argument("--profile", required=True, choices=["art-smoke"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        manifest = load_json(Path(args.manifest))
        receipt = build_receipt(manifest, generated_at=args.generated_at)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    write_json(receipt, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
