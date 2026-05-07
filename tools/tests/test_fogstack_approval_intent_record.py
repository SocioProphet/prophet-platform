from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema


SCHEMA = Path("schemas/runtime/fogstack-approval-intent-record-v0.1.schema.json")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def validate_record(record: dict) -> None:
    jsonschema.validate(record, read_json(SCHEMA))


def apply_plan(path: Path, *, safe: bool) -> None:
    write_json(path, {
        "kind": "FogStackLiveApplyPlanRecord",
        "schema_version": "v0.1",
        "status": "blocked",
        "mode": "plan-only",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "namespace": "fogstack-access",
        "target": "kubernetes",
        "safety": {
            "plan_only": True,
            "run_performed": False,
            "mutated_cluster": False,
            "live_apply_allowed": not safe,
            "future_approval_record_required": True,
            "rollback_plan_required": True,
        },
    })


def run_intent(tmp_path: Path, *, safe: bool) -> subprocess.CompletedProcess[str]:
    plan_path = tmp_path / "apply-plan.json"
    output = tmp_path / "approval-intent.json"
    apply_plan(plan_path, safe=safe)
    return subprocess.run([
        sys.executable,
        "tools/emit_fogstack_approval_intent_record.py",
        "--apply-plan", str(plan_path),
        "--output", str(output),
        "--requester", "human:test-operator",
        "--reason", "Test intent record only.",
        "--approval-window", "test-window-required",
    ], capture_output=True, text=True)


def test_approval_intent_record_from_safe_plan(tmp_path: Path) -> None:
    proc = run_intent(tmp_path, safe=True)
    assert proc.returncode == 0, proc.stderr
    record = read_json(tmp_path / "approval-intent.json")
    validate_record(record)
    assert record["kind"] == "FogStackApprovalIntentRecord"
    assert record["status"] == "recorded"
    assert record["mode"] == "intent-only"
    assert record["requester"] == "human:test-operator"
    assert record["bundle_id"] == "fogstack.access"
    assert record["safety"]["intent_only"] is True
    assert record["safety"]["authorizes_execution"] is False
    assert record["safety"]["run_performed"] is False
    assert record["safety"]["mutated_cluster"] is False
    assert record["safety"]["live_apply_allowed"] is False
    assert record["safety"]["requires_policyplane_execute_decision"] is True
    assert record["safety"]["requires_agentplane_execution_run"] is True
    assert record["safety"]["requires_rollback_plan"] is True
    assert record["safety"]["requires_external_identity_binding"] is True
    assert record["source_artifacts"][0]["id"] == "live-apply-plan-record"
    assert record["source_artifacts"][0]["digest"].startswith("sha256:")


def test_approval_intent_rejects_unsafe_plan(tmp_path: Path) -> None:
    proc = run_intent(tmp_path, safe=False)
    assert proc.returncode == 1
    assert "unsafe for approval intent" in proc.stderr
    assert not (tmp_path / "approval-intent.json").exists()
