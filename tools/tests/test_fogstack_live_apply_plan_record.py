from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema


SCHEMA = Path("schemas/runtime/fogstack-live-apply-plan-record-v0.1.schema.json")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def validate_record(record: dict) -> None:
    jsonschema.validate(record, read_json(SCHEMA))


def deploy_plan(path: Path) -> None:
    write_json(path, {
        "kind": "FogStackDeployPlan",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "namespace": "fogstack-access",
        "target": "kubernetes",
    })


def preflight(path: Path, status: str) -> None:
    write_json(path, {
        "kind": "FogStackLiveClusterPreflightRecord",
        "schema_version": "v0.1",
        "status": status,
        "reason": None if status == "passed" else "test blocked fixture",
        "namespace": "fogstack-access",
        "mode": "read-only-live-preflight",
        "kubectl": {"executable": "kubectl", "available": status == "passed", "resolved_path": "/tmp/kubectl" if status == "passed" else None},
        "source_artifacts": [],
        "safety": {
            "mutation_mode": "read-only",
            "mutated_cluster": False,
            "live_apply_allowed": False,
            "human_approval_required_for_apply": True,
        },
        "checks": [],
        "read_operations": [],
        "errors": [],
    })


def run_plan(tmp_path: Path, status: str, *extra: str) -> subprocess.CompletedProcess[str]:
    plan_path = tmp_path / "deploy-plan.json"
    preflight_path = tmp_path / "preflight.json"
    output = tmp_path / "apply-plan.json"
    deploy_plan(plan_path)
    preflight(preflight_path, status)
    return subprocess.run([
        sys.executable,
        "tools/emit_fogstack_live_apply_plan_record.py",
        "--deploy-plan", str(plan_path),
        "--live-preflight", str(preflight_path),
        "--output", str(output),
        *extra,
    ], capture_output=True, text=True)


def test_live_apply_plan_blocks_when_preflight_is_blocked(tmp_path: Path) -> None:
    proc = run_plan(tmp_path, "blocked")
    assert proc.returncode == 0, proc.stderr
    record = read_json(tmp_path / "apply-plan.json")
    validate_record(record)
    assert record["kind"] == "FogStackLiveApplyPlanRecord"
    assert record["status"] == "blocked"
    assert record["mode"] == "plan-only"
    assert record["live_preflight_status"] == "blocked"
    assert record["safety"]["plan_only"] is True
    assert record["safety"]["run_performed"] is False
    assert record["safety"]["mutated_cluster"] is False
    assert record["safety"]["live_apply_allowed"] is False
    assert record["blockers"] == ["live preflight is blocked"]


def test_live_apply_plan_passes_when_preflight_passes(tmp_path: Path) -> None:
    proc = run_plan(tmp_path, "passed")
    assert proc.returncode == 0, proc.stderr
    record = read_json(tmp_path / "apply-plan.json")
    validate_record(record)
    assert record["status"] == "passed"
    assert record["live_preflight_status"] == "passed"
    assert record["blockers"] == []
    assert record["agentplane"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert record["policyplane"]["policyplane_ref"] == "github://SocioProphet/policy-fabric"
    assert record["policyplane"]["decision"] == "allow-plan-deny-run"
    assert record["planned_resources"] == ["ConfigMap", "Deployment", "Service"]


def test_live_apply_plan_require_ready_fails_when_preflight_is_blocked(tmp_path: Path) -> None:
    proc = run_plan(tmp_path, "blocked", "--require-ready")
    assert proc.returncode == 1
    record = read_json(tmp_path / "apply-plan.json")
    validate_record(record)
    assert record["status"] == "blocked"
