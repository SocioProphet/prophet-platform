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


def artifact(path: Path, artifact_id: str) -> dict[str, str]:
    path = resolve(path)
    if not path.exists() or not path.is_file():
        raise SystemExit(f"ERR: required artifact missing: {path}")
    return {"id": artifact_id, "ref": rel(path), "digest": sha256_file(path)}


def preflight_safe(preflight: dict[str, Any]) -> bool:
    safety = preflight.get("safety") if isinstance(preflight.get("safety"), dict) else {}
    return (
        preflight.get("kind") == "FogStackLiveClusterPreflightRecord"
        and preflight.get("mode") == "read-only-live-preflight"
        and preflight.get("status") in {"passed", "blocked"}
        and safety.get("mutated_cluster") is False
        and safety.get("live_apply_allowed") is False
    )


def preflight_ready(preflight: dict[str, Any]) -> bool:
    return preflight_safe(preflight) and preflight.get("status") == "passed"


def emit_record(
    *,
    deploy_plan_path: Path,
    live_preflight_path: Path,
    output_path: Path,
    agentplane_ref: str,
    policyplane_ref: str,
    requested_by: str,
) -> dict[str, Any]:
    deploy_plan_path = resolve(deploy_plan_path)
    live_preflight_path = resolve(live_preflight_path)
    output_path = resolve(output_path)
    deploy_plan = load_json(deploy_plan_path)
    preflight = load_json(live_preflight_path)
    if deploy_plan.get("kind") != "FogStackDeployPlan":
        raise SystemExit("ERR: expected FogStackDeployPlan")
    if not preflight_safe(preflight):
        raise SystemExit("ERR: live preflight record is unsafe for planning")

    ready = preflight_ready(preflight)
    record = {
        "kind": "FogStackLiveApplyPlanRecord",
        "schema_version": "v0.1",
        "status": "passed" if ready else "blocked",
        "mode": "plan-only",
        "bundle_id": deploy_plan.get("bundle_id"),
        "version": deploy_plan.get("version"),
        "namespace": deploy_plan.get("namespace") or preflight.get("namespace"),
        "target": deploy_plan.get("target"),
        "deploy_plan_ref": rel(deploy_plan_path),
        "deploy_plan_digest": sha256_file(deploy_plan_path),
        "live_preflight_ref": rel(live_preflight_path),
        "live_preflight_digest": sha256_file(live_preflight_path),
        "live_preflight_status": preflight.get("status"),
        "agentplane": {
            "agentplane_ref": agentplane_ref,
            "requested_by": requested_by,
            "mode": "plan-only",
            "future_execution_run_required": True,
        },
        "policyplane": {
            "policyplane_ref": policyplane_ref,
            "decision": "allow-plan-deny-run",
            "future_execute_decision_required": True,
            "human_approval_required": True,
        },
        "safety": {
            "plan_only": True,
            "run_performed": False,
            "mutated_cluster": False,
            "live_apply_allowed": False,
            "future_approval_record_required": True,
            "rollback_plan_required": True,
        },
        "planned_resources": ["ConfigMap", "Deployment", "Service"],
        "blockers": [] if ready else ["live preflight is blocked"],
        "source_artifacts": [
            artifact(deploy_plan_path, "deploy-plan"),
            artifact(live_preflight_path, "live-cluster-preflight-record"),
        ],
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a plan-only FogStack live apply plan record")
    parser.add_argument("--deploy-plan", required=True, type=Path)
    parser.add_argument("--live-preflight", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--agentplane-ref", default="github://SocioProphet/agentplane")
    parser.add_argument("--policyplane-ref", default="github://SocioProphet/policy-fabric")
    parser.add_argument("--requested-by", default="human:operator")
    args = parser.parse_args()

    record = emit_record(
        deploy_plan_path=args.deploy_plan,
        live_preflight_path=args.live_preflight,
        output_path=args.output,
        agentplane_ref=args.agentplane_ref,
        policyplane_ref=args.policyplane_ref,
        requested_by=args.requested_by,
    )
    print(json.dumps(record, indent=2))
    if args.require_ready and record["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
