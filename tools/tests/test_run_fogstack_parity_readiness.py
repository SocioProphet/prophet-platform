from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_run_fogstack_parity_readiness(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    proc = subprocess.run([
        sys.executable,
        "tools/run_fogstack_parity_readiness.py",
        "--output-dir", str(output_dir),
        "--summary",
    ], check=True, capture_output=True, text=True)
    assert "FogStack parity readiness: passed" in proc.stdout
    assert "Parity target: credible-mvp-ibm-style-parity" in proc.stdout
    assert "Turn counter: 31/32" in proc.stdout
    record_path = output_dir / "fogstack-parity-readiness.record.json"
    assert record_path.exists()
    record = load(record_path)
    assert record["kind"] == "FogStackParityReadinessRecord"
    assert record["status"] == "passed"
    assert record["errors"] == []
    assert "live_apply_plan" in {lane["id"] for lane in record["checked_lanes"]}
    assert "live_apply_plan_record" in record["required_summary_artifacts"]
    assert "deploy_live_apply_plan_record" in record["required_index_ids"]

    full_summary = load(output_dir / "fogstack-local-demo.full.summary.json")
    assert "live_apply_plan_record" in full_summary["artifacts"]
    apply_plan = load(Path(full_summary["artifacts"]["live_apply_plan_record"]))
    assert apply_plan["kind"] == "FogStackLiveApplyPlanRecord"
    assert apply_plan["mode"] == "plan-only"
    assert apply_plan["safety"]["run_performed"] is False
    assert apply_plan["safety"]["mutated_cluster"] is False
    assert apply_plan["safety"]["live_apply_allowed"] is False

    index = load(output_dir / "demo-artifacts.index.json")
    assert "deploy_live_apply_plan_record" in {entry["id"] for entry in index["artifacts"]}
