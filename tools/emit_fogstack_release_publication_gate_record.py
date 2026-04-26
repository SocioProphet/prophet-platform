#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def record(checks: list[dict[str, str]], rule_id: str, status: str, message: str) -> None:
    checks.append({"id": rule_id, "status": status, "message": message})


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Fog Stack release publication gate")
    parser.add_argument("--publication-set", required=True, type=Path)
    parser.add_argument("--approval-record", required=True, type=Path)
    parser.add_argument("--approval-signature-verification", required=True, type=Path)
    parser.add_argument("--release-identity", required=True, type=Path)
    parser.add_argument("--policy-catalog", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    publication = load_json(args.publication_set)
    approval = load_json(args.approval_record)
    sig_verify = load_json(args.approval_signature_verification)
    identity = load_json(args.release_identity)
    policy = yaml.safe_load(args.policy_catalog.read_text(encoding="utf-8")) or {}
    requirements = policy.get("requirements") or {}

    checks: list[dict[str, str]] = []

    expected_status = requirements.get("approval_status", "approved")
    if approval.get("status") == expected_status:
        record(checks, "PUBGATE-001", "pass", "approval status matches policy")
    else:
        record(checks, "PUBGATE-001", "fail", "approval status does not match policy")

    expected_sig_status = requirements.get("approval_signature_status", "pass")
    if sig_verify.get("status") == expected_sig_status:
        record(checks, "PUBGATE-002", "pass", "approval signature verification passed")
    else:
        record(checks, "PUBGATE-002", "fail", "approval signature verification did not pass")

    if requirements.get("require_release_identity", True):
        allowed = policy.get("allowed_release_identities") or []
        identity_tuple = (identity.get("id"), identity.get("issuer"), identity.get("subject"))
        allowed_tuples = {
            (item.get("id"), item.get("issuer"), item.get("subject"))
            for item in allowed
            if isinstance(item, dict)
        }
        if identity_tuple in allowed_tuples:
            record(checks, "PUBGATE-003", "pass", "release identity is allowed")
        else:
            record(checks, "PUBGATE-003", "fail", "release identity is not allowed")

    if publication.get("kind") == "FogStackManifestPublicationSet":
        record(checks, "PUBGATE-004", "pass", "publication set kind is valid")
    else:
        record(checks, "PUBGATE-004", "fail", "publication set kind is invalid")

    status = "fail" if any(item["status"] == "fail" for item in checks) else "pass"
    gate = {
        "kind": "FogStackReleasePublicationGateRecord",
        "schema_version": "v0.1",
        "publication_set_ref": str(args.publication_set),
        "approval_record_ref": str(args.approval_record),
        "approval_signature_verification_ref": str(args.approval_signature_verification),
        "release_identity_ref": str(args.release_identity),
        "status": status,
        "checks": checks,
    }

    text = json.dumps(gate, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
