#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "prophet-mesh" / "demo" / "prophet-mesh-runtime-readiness.v0.json"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "prophet-mesh-runtime-readout"

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


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_fixture(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runtime_path = record.get("runtime_path", {})

    if record.get("readiness_state") != "ready_for_nonprod_eval":
        errors.append("readiness_state must be ready_for_nonprod_eval")
    for key in (
        "production_ready",
        "external_action_allowed",
        "live_provider_call",
        "provider_secrets_required",
        "real_user_data_processing",
        "customer_facing_claim",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("requires_human_approval") is not True:
        errors.append("requires_human_approval must be true")
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

    text = json.dumps(record, sort_keys=True)
    for token in ("sk-", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "BEGIN PRIVATE KEY"):
        if token in text:
            errors.append(f"fixture must not contain secret marker: {token}")

    return errors


def build_artifact(record: dict[str, Any], fixture_hash: str) -> dict[str, Any]:
    runtime_path = record["runtime_path"]
    return {
        "artifact_version": "0.1.0",
        "artifact_id": "prophet_mesh_runtime_readout_demo_artifact_v0",
        "artifact_kind": "nonprod_runtime_readout",
        "deterministic": True,
        "generated_by": "tools/run_prophet_mesh_runtime_readout_demo.py",
        "source_fixture": "contracts/prophet-mesh/demo/prophet-mesh-runtime-readiness.v0.json",
        "source_fixture_sha256": fixture_hash,
        "readiness_state": record["readiness_state"],
        "posture": {
            "production_ready": record["production_ready"],
            "external_action_allowed": record["external_action_allowed"],
            "live_provider_call": record["live_provider_call"],
            "provider_secrets_required": record["provider_secrets_required"],
            "real_user_data_processing": record["real_user_data_processing"],
            "customer_facing_claim": record["customer_facing_claim"],
            "requires_human_approval": record["requires_human_approval"],
        },
        "runtime_path": runtime_path,
        "demo_surface": record["demo_surface"],
        "blocked_actions": record["blocked_actions"],
        "upstream_artifacts": record["upstream_artifacts"],
        "created_at": record["created_at"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit the deterministic Prophet Mesh runtime readout demo artifact.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for emitted demo artifacts.")
    parser.add_argument("--summary", action="store_true", help="Print a short artifact summary.")
    args = parser.parse_args()

    fixture_bytes = FIXTURE.read_bytes()
    fixture_hash = sha256_bytes(fixture_bytes)
    record = read_json(FIXTURE)

    errors = validate_fixture(record)
    if errors:
        print("ERR: cannot emit runtime readout demo artifact", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact = build_artifact(record, fixture_hash)
    artifact_bytes = canonical_json_bytes(artifact)
    artifact_path = output_dir / "runtime-readout.json"
    artifact_path.write_bytes(artifact_bytes)

    manifest = {
        "manifest_version": "0.1.0",
        "manifest_id": "prophet_mesh_runtime_readout_demo_manifest_v0",
        "deterministic": True,
        "source_fixture": "contracts/prophet-mesh/demo/prophet-mesh-runtime-readiness.v0.json",
        "source_fixture_sha256": fixture_hash,
        "artifacts": [
            {
                "path": "runtime-readout.json",
                "kind": "nonprod_runtime_readout",
                "sha256": sha256_bytes(artifact_bytes),
            }
        ],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    if args.summary:
        print("Prophet Mesh runtime readout demo artifact emitted.")
        print(f"artifact: {artifact_path}")
        print(f"manifest: {manifest_path}")
        print(f"source_fixture_sha256: {fixture_hash}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
