#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_report() -> dict[str, Any]:
    generated_at = "2026-05-05T00:00:00Z"
    return {
        "schema": "sourceos.state-integrity-report/v1alpha1",
        "generated_at": generated_at,
        "identity": {
            "component": "sourceos-syncd",
            "repo": "github://SourceOS-Linux/sourceos-syncd",
            "pid": 0,
            "process_name": "sourceos-syncd-demo",
            "node_id_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "boot_id": None,
            "version": "0.1.0-demo",
            "commit": None,
            "build_provenance": "github://SourceOS-Linux/sourceos-syncd",
            "platform": "unknown",
            "service_manager": "manual",
        },
        "collection": {
            "status": "complete",
            "duration_ms": 0,
            "errors": [],
            "redacted_fields": [],
            "permission_denied_fields": [],
            "timed_out_fields": [],
            "unavailable_fields": [],
        },
        "runtime": {
            "process_started_at": generated_at,
            "runtime_ready_at": generated_at,
            "store_opened_at": generated_at,
            "replay_started_at": generated_at,
            "replay_completed_at": generated_at,
            "first_heartbeat_at": generated_at,
            "last_heartbeat_at": generated_at,
            "last_clean_shutdown_at": None,
            "last_dirty_open_at": None,
        },
        "stores": [
            {
                "name": "sourceos-local-state-demo",
                "role": "active",
                "backend": "fixture",
                "schema_version": "v1alpha1",
                "created_by_version": "0.1.0-demo",
                "runtime_version": "0.1.0-demo",
                "previous_runtime_version": None,
                "migration_state": "none",
                "active_generation": 1,
                "last_known_good_generation": 1,
                "shadow_present": False,
                "manifest_present": True,
                "checksum_state": "verified",
                "flags_raw": 0,
                "flags_hex": "0x0",
                "flags_decoded": [],
                "unknown_flags": [],
            }
        ],
        "lanes": [
            {
                "name": "policy",
                "status": "active",
                "sla": {"max_staleness_seconds": 60},
                "objects": {"total": 3, "verified": 3, "stale": 0, "unsafe": 0},
                "journal": {"status": "verified", "entries": 3, "last_sequence": 3},
                "maintenance": {"repair_required": False, "last_compaction_at": generated_at},
            },
            {
                "name": "audit",
                "status": "active",
                "sla": {"max_staleness_seconds": 300},
                "objects": {"total": 4, "verified": 4, "stale": 0, "unsafe": 0},
                "journal": {"status": "verified", "entries": 4, "last_sequence": 4},
                "maintenance": {"repair_required": False, "last_compaction_at": generated_at},
            },
        ],
        "pipeline": {
            "mode": "bounded-local-demo",
            "source": "FogStack full local demo",
            "upstream_contract": "github://SourceOS-Linux/sourceos-syncd/schemas/sourceos.state-integrity-report.v1alpha1.schema.json",
            "mutating_repairs_enabled": False,
        },
        "resources": {
            "disk": {
                "filesystem": "demo",
                "free_bytes": 1024,
                "total_bytes": 4096,
                "free_ratio": 0.25,
                "pressure": "none",
            },
            "memory": {
                "pressure": "none",
                "working_set_bytes": 0,
            },
        },
        "policy": {
            "policy_engine": "github://SocioProphet/policy-fabric",
            "policy_decisions": {
                "allow": 3,
                "deny": 0,
                "manual_review": 0,
                "blocked_expected": 1,
            },
        },
        "invariants": [
            {
                "id": "state-store-checksum-verified",
                "status": "pass",
                "severity": "info",
                "evidence": {"store": "sourceos-local-state-demo", "checksum_state": "verified"},
                "remediation": "No repair required for bounded local demo fixture.",
            },
            {
                "id": "repair-actions-disabled",
                "status": "pass",
                "severity": "info",
                "evidence": {"mutating_repairs_enabled": False},
                "remediation": "Keep repair apply disabled unless a signed approval plan exists.",
            },
        ],
        "diagnosis": {
            "status": "healthy",
            "summary": "SourceOS state-integrity fixture is healthy and non-mutating for the FogStack local demo.",
            "operator_narrative": "State integrity is present as digest-indexed evidence. Repair apply remains disabled by policy.",
        },
        "controls": [
            {
                "id": "repair-apply-disabled",
                "status": "enforced",
                "policy_ref": "github://SocioProphet/policy-fabric",
            },
            {
                "id": "artifact-index-required",
                "status": "enforced",
                "policy_ref": "github://SocioProphet/prophet-platform/tools/check_fogstack_local_demo_artifact_index.py",
            },
        ],
        "attestation": {
            "status": "demo-evidence",
            "artifact_indexed": True,
            "source_repo": "github://SourceOS-Linux/sourceos-syncd",
            "consumer_repo": "github://SocioProphet/prophet-platform",
        },
    }


def update_artifact_index(index_path: Path, artifact_id: str, artifact_path: Path) -> None:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or not isinstance(index.get("artifacts"), list):
        raise SystemExit(f"ERR: malformed artifact index: {index_path}")

    artifact_ref = rel(artifact_path)
    entry = {
        "id": artifact_id,
        "ref": artifact_ref,
        "digest": sha256_file(artifact_path),
        "size_bytes": artifact_path.stat().st_size,
    }

    for existing in index["artifacts"]:
        if not isinstance(existing, dict):
            continue
        if existing.get("id") == artifact_id or existing.get("ref") == artifact_ref:
            existing.update(entry)
            write_json(index_path, index)
            return

    index["artifacts"].append(entry)
    write_json(index_path, index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a SourceOS state-integrity report for the FogStack local demo")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--artifact-index", type=Path)
    parser.add_argument("--artifact-id", default="sourceos_state_integrity_report")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else ROOT / args.output
    write_json(output, build_report())

    if args.artifact_index:
        index_path = args.artifact_index if args.artifact_index.is_absolute() else ROOT / args.artifact_index
        update_artifact_index(index_path, args.artifact_id, output)

    if args.summary:
        print(f"SourceOS state integrity report: {rel(output)}")
        if args.artifact_index:
            print(f"Artifact index updated: {rel(index_path)}")
    else:
        print(json.dumps({"status": "passed", "report": rel(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
