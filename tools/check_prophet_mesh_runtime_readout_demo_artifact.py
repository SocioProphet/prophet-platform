#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "build" / "prophet-mesh-runtime-readout"
FIXTURE = ROOT / "contracts" / "prophet-mesh" / "demo" / "prophet-mesh-runtime-readiness.v0.json"

REQUIRED_CONTROLS = (
    "identity",
    "policy",
    "evidence",
    "attestation",
    "revocation",
    "audit",
    "tenant_isolation",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate emitted Prophet Mesh runtime readout demo artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory containing emitted demo artifacts.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    artifact_path = output_dir / "runtime-readout.json"
    manifest_path = output_dir / "manifest.json"

    errors: list[str] = []
    if not artifact_path.is_file():
        errors.append(f"missing artifact: {artifact_path}")
    if not manifest_path.is_file():
        errors.append(f"missing manifest: {manifest_path}")
    if errors:
        for error in errors:
            print(f"ERR: {error}", file=sys.stderr)
        return 2

    artifact_bytes = artifact_path.read_bytes()
    manifest = read_json(manifest_path)
    artifact = read_json(artifact_path)
    fixture = read_json(FIXTURE)
    fixture_hash = sha256_bytes(FIXTURE.read_bytes())

    if manifest.get("manifest_version") != "0.1.0":
        errors.append("manifest_version must be 0.1.0")
    if manifest.get("deterministic") is not True:
        errors.append("manifest.deterministic must be true")
    if manifest.get("source_fixture_sha256") != fixture_hash:
        errors.append("manifest source fixture hash mismatch")

    artifacts = manifest.get("artifacts", [])
    if len(artifacts) != 1:
        errors.append("manifest must contain exactly one artifact")
    else:
        item = artifacts[0]
        if item.get("path") != "runtime-readout.json":
            errors.append("manifest artifact path must be runtime-readout.json")
        if item.get("sha256") != sha256_bytes(artifact_bytes):
            errors.append("manifest artifact hash mismatch")

    if artifact.get("artifact_version") != "0.1.0":
        errors.append("artifact_version must be 0.1.0")
    if artifact.get("artifact_kind") != "nonprod_runtime_readout":
        errors.append("artifact_kind must be nonprod_runtime_readout")
    if artifact.get("deterministic") is not True:
        errors.append("artifact.deterministic must be true")
    if artifact.get("source_fixture_sha256") != fixture_hash:
        errors.append("artifact source fixture hash mismatch")
    if artifact.get("readiness_state") != fixture.get("readiness_state"):
        errors.append("artifact readiness_state must match fixture")

    posture = artifact.get("posture", {})
    for key in (
        "production_ready",
        "external_action_allowed",
        "live_provider_call",
        "provider_secrets_required",
        "real_user_data_processing",
        "customer_facing_claim",
    ):
        if posture.get(key) is not False:
            errors.append(f"posture.{key} must be false")
    if posture.get("requires_human_approval") is not True:
        errors.append("posture.requires_human_approval must be true")

    runtime_path = artifact.get("runtime_path", {})
    if runtime_path.get("policy_decision") != "requires_approval":
        errors.append("runtime_path.policy_decision must be requires_approval")
    if runtime_path.get("execution_trace_status") != "awaiting_approval":
        errors.append("runtime_path.execution_trace_status must be awaiting_approval")
    if not runtime_path.get("evidence_refs"):
        errors.append("runtime_path.evidence_refs must be non-empty")
    if not runtime_path.get("audit_refs"):
        errors.append("runtime_path.audit_refs must be non-empty")

    controls = runtime_path.get("controls", {})
    for control in REQUIRED_CONTROLS:
        if controls.get(control) is not True:
            errors.append(f"runtime_path.controls.{control} must be true")

    text = artifact_path.read_text(encoding="utf-8") + manifest_path.read_text(encoding="utf-8")
    for token in ("sk-", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BEGIN PRIVATE KEY"):
        if token in text:
            errors.append(f"demo artifact must not contain secret marker: {token}")

    if errors:
        print("ERR: Prophet Mesh runtime readout demo artifact validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print("Prophet Mesh runtime readout demo artifact validates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
