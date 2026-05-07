from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def add_apply_plan_to_full_summary(output_dir: Path) -> None:
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_apply_plan.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json")], check=True)
    local_summary = load(output_dir / "fogstack-local-demo.summary.json")
    full_summary_path = output_dir / "fogstack-local-demo.full.summary.json"
    full_summary = load(full_summary_path)
    apply_ref = local_summary["artifacts"]["deploy_live_apply_plan_record"]
    full_summary.setdefault("artifacts", {})["live_apply_plan_record"] = apply_ref
    checks = full_summary.setdefault("checks", [])
    for check in ["live_apply_plan_record_indexed", "live_apply_plan_summary_appended"]:
        if check not in checks:
            checks.append(check)
    write(full_summary_path, full_summary)


def test_check_fogstack_parity_readiness(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"], check=True)
    add_apply_plan_to_full_summary(output_dir)
    record_path = output_dir / "fogstack-parity-readiness.record.json"
    proc = subprocess.run([sys.executable, "tools/check_fogstack_parity_readiness.py", "--summary", str(output_dir / "fogstack-local-demo.full.summary.json"), "--index", str(output_dir / "demo-artifacts.index.json"), "--output", str(record_path), "--summary-text"], check=True, capture_output=True, text=True)
    assert "FogStack parity readiness: passed" in proc.stdout
    record = load(record_path)
    assert record["kind"] == "FogStackParityReadinessRecord"
    assert record["status"] == "passed"
    assert record["errors"] == []
    checked = {lane["id"] for lane in record["checked_lanes"]}
    for lane in ["node_inventory", "immutable_update_readiness", "cluster_readiness", "gitops_readiness", "live_cluster_preflight", "live_apply_plan", "runtime_adapter", "runtime_dry_run", "deploy_plan", "agent_corps_plan", "gitops_bundle", "gitops_application", "gitops_kustomization"]:
        assert lane in checked
    for artifact_id in ["deploy_runtime_dry_run_record", "deploy_node_inventory_record", "deploy_immutable_update_readiness_record", "deploy_live_cluster_preflight_record", "deploy_live_apply_plan_record"]:
        assert artifact_id in record["required_index_ids"]
    assert "live_cluster_preflight_record" in record["required_summary_artifacts"]
    assert "live_apply_plan_record" in record["required_summary_artifacts"]


def test_check_fogstack_parity_readiness_fails_without_apply_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"], check=True)
    record_path = output_dir / "fogstack-parity-readiness.record.json"
    proc = subprocess.run([sys.executable, "tools/check_fogstack_parity_readiness.py", "--summary", str(output_dir / "fogstack-local-demo.full.summary.json"), "--index", str(output_dir / "demo-artifacts.index.json"), "--output", str(record_path), "--summary-text"], capture_output=True, text=True)
    assert proc.returncode == 1
    record = load(record_path)
    assert record["status"] == "failed"
    assert "missing summary artifact: live_apply_plan_record" in record["errors"]
    assert "artifact index missing id: deploy_live_apply_plan_record" in record["errors"]
