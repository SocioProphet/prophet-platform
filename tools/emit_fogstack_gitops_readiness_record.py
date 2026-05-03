#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_status(value: str) -> str:
    allowed = {"passed", "failed", "skipped"}
    if value not in allowed:
        raise SystemExit(f"ERR: invalid status {value}; expected one of {sorted(allowed)}")
    return value


def emit_record(bundle_path: Path, output_path: Path, generator_status: str, checker_status: str, checker_message: str) -> dict[str, Any]:
    bundle_path = bundle_path if bundle_path.is_absolute() else ROOT / bundle_path
    output_path = output_path if output_path.is_absolute() else ROOT / output_path
    bundle = load_json(bundle_path)
    if bundle.get("kind") != "FogStackGitOpsBundle":
        raise SystemExit("ERR: expected FogStackGitOpsBundle")

    generator_status = normalize_status(generator_status)
    checker_status = normalize_status(checker_status)
    status = "passed" if generator_status == "passed" and checker_status == "passed" else "failed"
    record = {
        "kind": "FogStackGitOpsReadinessRecord",
        "schema_version": "v0.1",
        "status": status,
        "bundle_id": bundle["bundle_id"],
        "version": bundle["version"],
        "namespace": bundle["namespace"],
        "gitops_bundle_ref": rel(bundle_path),
        "gitops_bundle_digest": sha256_file(bundle_path),
        "deploy_plan_ref": bundle["deploy_plan_ref"],
        "deploy_plan_digest": bundle["deploy_plan_digest"],
        "agent_corps_plan_ref": bundle["agent_corps_plan_ref"],
        "agent_corps_plan_digest": bundle["agent_corps_plan_digest"],
        "source": bundle["source"],
        "application_ref": bundle["application"]["ref"],
        "application_digest": bundle["application"]["digest"],
        "kustomization_ref": bundle["kustomization"]["ref"],
        "kustomization_digest": bundle["kustomization"]["digest"],
        "manifest_count": len(bundle["manifests"]),
        "artifact_count": len(bundle["artifacts"]),
        "generator": {
            "status": generator_status,
        },
        "checker": {
            "status": checker_status,
            "message": checker_message,
        },
        "validation_result": {
            "status": checker_status,
            "bundle_validated": checker_status == "passed",
        },
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a FogStack GitOps readiness record")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generator-status", choices=["passed", "failed", "skipped"], default="passed")
    parser.add_argument("--checker-status", choices=["passed", "failed", "skipped"], default="passed")
    parser.add_argument("--checker-message", default="FogStack GitOps bundle passed.")
    args = parser.parse_args()

    record = emit_record(args.bundle, args.output, args.generator_status, args.checker_status, args.checker_message)
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
