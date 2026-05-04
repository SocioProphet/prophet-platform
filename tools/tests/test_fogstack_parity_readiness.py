from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_fogstack_parity_readiness(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"], check=True)
    record_path = output_dir / "fogstack-parity-readiness.record.json"
    proc = subprocess.run([sys.executable, "tools/check_fogstack_parity_readiness.py", "--summary", str(output_dir / "fogstack-local-demo.full.summary.json"), "--index", str(output_dir / "demo-artifacts.index.json"), "--output", str(record_path), "--summary-text"], check=True, capture_output=True, text=True)
    assert "FogStack parity readiness: passed" in proc.stdout
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["kind"] == "FogStackParityReadinessRecord"
    assert record["status"] == "passed"
    assert record["errors"] == []
    checked = {lane["id"] for lane in record["checked_lanes"]}
    for lane in ["node_inventory", "immutable_update_readiness", "cluster_readiness", "gitops_readiness", "runtime_adapter", "runtime_dry_run", "deploy_plan", "agent_corps_plan", "gitops_bundle", "gitops_application", "gitops_kustomization"]:
        assert lane in checked
    for artifact_id in ["deploy_runtime_dry_run_record", "deploy_node_inventory_record", "deploy_immutable_update_readiness_record"]:
        assert artifact_id in record["required_index_ids"]
