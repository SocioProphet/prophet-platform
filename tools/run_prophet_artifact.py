#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = ROOT / "contracts/computational-artifacts/prophet-artifact.v1alpha1.example.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "build/prophet-artifact"

from prophet_artifact_contract import (  # noqa: E402
    EXPECTED_EVIDENCE_FILES,
    ValidationError,
    load_manifest,
    stable_run_id,
    validate_manifest,
)


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_action(action: dict[str, Any], allow_privileged: bool) -> dict[str, Any]:
    privileged = bool(action.get("privileged", False))
    if privileged and not allow_privileged:
        raise ValidationError(
            f"action '{action['id']}' is privileged and blocked; pass --allow-privileged to permit"
        )
    mode = action.get("mode", "noop")
    if mode == "fixture":
        return {
            "action_id": action["id"],
            "verb": action["verb"],
            "status": "succeeded",
            "executor": "fixture",
            "privileged": privileged,
            "summary": "fixture-safe action executed without external mutation",
        }
    if mode == "noop":
        return {
            "action_id": action["id"],
            "verb": action["verb"],
            "status": "skipped",
            "executor": "noop",
            "privileged": privileged,
            "summary": "no-op action acknowledged",
        }
    raise ValidationError(f"action '{action['id']}' mode '{mode}' is not supported")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded local-safe ProphetArtifact actions")
    parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT), help="Path to prophet-artifact.yaml")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for evidence outputs")
    parser.add_argument("--allow-privileged", action="store_true", help="Permit actions marked privileged")
    args = parser.parse_args()

    artifact_path = Path(args.artifact).expanduser()
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    try:
        manifest = load_manifest(artifact_path)
        parsed = validate_manifest(manifest)
        action_results = [execute_action(action, allow_privileged=args.allow_privileged) for action in parsed["actions"]]
    except ValidationError as exc:
        fail(str(exc))

    run_id = stable_run_id(manifest)
    run_record_path = output_dir / "run-record.json"
    validation_path = output_dir / "validation-report.json"
    benchmark_path = output_dir / "benchmark-report.json"
    sociosphere_path = output_dir / "sociosphere-registration.json"
    sherlock_path = output_dir / "sherlock-index-payload.json"
    scoreboard_path = output_dir / "delivery-excellence-scoreboard-payload.json"
    checksums_path = output_dir / "checksums.json"

    run_record = {
        "kind": "ProphetArtifactRunRecord",
        "run_id": run_id,
        "artifact": {
            "name": parsed["metadata"]["name"],
            "version": parsed["metadata"]["version"],
            "path": str(artifact_path.relative_to(ROOT) if artifact_path.is_relative_to(ROOT) else artifact_path),
        },
        "policy": {
            "allow_privileged": args.allow_privileged,
            "manifest_allow_privileged": parsed["policy"]["allowPrivilegedActions"],
            "safety_class": parsed["policy"]["safetyClass"],
            "network": parsed["policy"]["network"],
        },
        "actions": action_results,
        "status": "succeeded",
    }
    validation = {
        "kind": "ProphetArtifactValidationReport",
        "run_id": run_id,
        "status": "passed",
        "required_sections": ["metadata", "actions", "provenance", "policy", "evidence"],
        "required_outputs": EXPECTED_EVIDENCE_FILES,
    }
    benchmark = {
        "kind": "ProphetArtifactBenchmarkReport",
        "run_id": run_id,
        "status": "passed",
        "metrics": {
            "action_count": len(action_results),
            "executed_fixture_actions": sum(1 for item in action_results if item["executor"] == "fixture"),
            "noop_actions": sum(1 for item in action_results if item["executor"] == "noop"),
        },
    }
    sociosphere = {
        "kind": "SociosphereArtifactRegistrationPayload",
        "run_id": run_id,
        "artifact_ref": f"artifact://{parsed['metadata']['name']}@{parsed['metadata']['version']}",
        "provenance": parsed["provenance"],
        "policy": {
            "safetyClass": parsed["policy"]["safetyClass"],
            "network": parsed["policy"]["network"],
        },
    }
    sherlock = {
        "kind": "SherlockIndexPayload",
        "run_id": run_id,
        "documents": [
            {
                "id": f"{run_id}:{item['action_id']}",
                "family": "prophet-artifact-action",
                "title": f"{item['verb']} action {item['action_id']}",
                "text": item["summary"],
                "status": item["status"],
            }
            for item in action_results
        ],
    }
    scoreboard = {
        "kind": "DeliveryExcellenceScoreboardPayload",
        "run_id": run_id,
        "artifact": parsed["metadata"]["name"],
        "version": parsed["metadata"]["version"],
        "metrics": {
            "artifact_runner_success": 1,
            "artifact_runner_actions_total": len(action_results),
            "artifact_runner_actions_privileged": sum(1 for item in action_results if item["privileged"]),
        },
        "state": "green",
    }

    write_json(run_record_path, run_record)
    write_json(validation_path, validation)
    write_json(benchmark_path, benchmark)
    write_json(sociosphere_path, sociosphere)
    write_json(sherlock_path, sherlock)
    write_json(scoreboard_path, scoreboard)

    checksums = {
        "kind": "ProphetArtifactChecksums",
        "run_id": run_id,
        "sha256": {
            "run-record.json": sha256(run_record_path),
            "validation-report.json": sha256(validation_path),
            "benchmark-report.json": sha256(benchmark_path),
            "sociosphere-registration.json": sha256(sociosphere_path),
            "sherlock-index-payload.json": sha256(sherlock_path),
            "delivery-excellence-scoreboard-payload.json": sha256(scoreboard_path),
        },
    }
    write_json(checksums_path, checksums)

    summary = {
        "ok": True,
        "run_id": run_id,
        "output_dir": str(output_dir),
        "outputs": EXPECTED_EVIDENCE_FILES,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
