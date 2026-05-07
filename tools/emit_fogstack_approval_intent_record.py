#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def source_artifact(path: Path, artifact_id: str) -> dict[str, str]:
    path = resolve(path)
    if not path.exists() or not path.is_file():
        raise SystemExit(f"ERR: required source artifact missing: {path}")
    return {"id": artifact_id, "ref": rel(path), "digest": sha256_file(path)}


def plan_is_safe(plan: dict[str, Any]) -> bool:
    safety = plan.get("safety") if isinstance(plan.get("safety"), dict) else {}
    return (
        plan.get("kind") == "FogStackLiveApplyPlanRecord"
        and plan.get("mode") == "plan-only"
        and plan.get("status") in {"passed", "blocked"}
        and safety.get("run_performed") is False
        and safety.get("mutated_cluster") is False
        and safety.get("live_apply_allowed") is False
    )


def emit_record(
    *,
    apply_plan_path: Path,
    output_path: Path,
    requester: str,
    reason: str,
    approval_window: str,
) -> dict[str, Any]:
    apply_plan_path = resolve(apply_plan_path)
    output_path = resolve(output_path)
    plan = load_json(apply_plan_path)
    if not plan_is_safe(plan):
        raise SystemExit("ERR: apply plan is unsafe for approval intent")

    record = {
        "kind": "FogStackApprovalIntentRecord",
        "schema_version": "v0.1",
        "status": "recorded",
        "mode": "intent-only",
        "bundle_id": plan.get("bundle_id"),
        "version": plan.get("version"),
        "namespace": plan.get("namespace"),
        "target": plan.get("target"),
        "requester": requester,
        "reason": reason,
        "approval_window": approval_window,
        "apply_plan_ref": rel(apply_plan_path),
        "apply_plan_digest": sha256_file(apply_plan_path),
        "source_artifacts": [source_artifact(apply_plan_path, "live-apply-plan-record")],
        "safety": {
            "intent_only": True,
            "authorizes_execution": False,
            "run_performed": False,
            "mutated_cluster": False,
            "live_apply_allowed": False,
            "requires_policyplane_execute_decision": True,
            "requires_agentplane_execution_run": True,
            "requires_rollback_plan": True,
            "requires_external_identity_binding": True,
        },
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a non-authorizing FogStack approval intent record")
    parser.add_argument("--apply-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--requester", default="human:operator")
    parser.add_argument("--reason", default="Operator requests a future execution review; this record does not authorize execution.")
    parser.add_argument("--approval-window", default="future-explicit-window-required")
    args = parser.parse_args()

    record = emit_record(
        apply_plan_path=args.apply_plan,
        output_path=args.output,
        requester=args.requester,
        reason=args.reason,
        approval_window=args.approval_window,
    )
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
