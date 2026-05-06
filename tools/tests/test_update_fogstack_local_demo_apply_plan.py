from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_update_fogstack_local_demo_apply_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    deploy_dir = output_dir / "deploy"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo.py", "--pack", "all", "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(deploy_dir)], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_deploy_artifacts.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--deploy-summary-json", str(deploy_dir / "fogstack.access.deploy-demo.summary.json")], check=True)
    proc = subprocess.run([sys.executable, "tools/update_fogstack_local_demo_apply_plan.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json")], check=True, capture_output=True, text=True)
    assert "FogStackLocalDemoApplyPlanUpdate" in proc.stdout

    summary = load(output_dir / "fogstack-local-demo.summary.json")
    assert "deploy_live_apply_plan_record" in summary["artifacts"]
    assert "live_apply_plan_record_emitted" in summary["checks"]
    assert "live_apply_plan_record_indexed" in summary["checks"]
    assert "live_apply_plan_summary_appended" in summary["checks"]

    plan_record = load(Path(summary["artifacts"]["deploy_live_apply_plan_record"]))
    assert plan_record["kind"] == "FogStackLiveApplyPlanRecord"
    assert plan_record["mode"] == "plan-only"
    assert plan_record["status"] == "blocked"
    assert plan_record["safety"]["run_performed"] is False
    assert plan_record["safety"]["mutated_cluster"] is False
    assert plan_record["safety"]["live_apply_allowed"] is False
    assert plan_record["safety"]["future_approval_record_required"] is True

    artifact_index = load(output_dir / "demo-artifacts.index.json")
    indexed = {entry["id"]: entry for entry in artifact_index["artifacts"]}
    assert "deploy_live_apply_plan_record" in indexed
    assert indexed["deploy_live_apply_plan_record"]["digest"].startswith("sha256:")
    assert Path(indexed["deploy_live_apply_plan_record"]["ref"]).exists()

    markdown = (output_dir / "fogstack-local-demo.summary.md").read_text(encoding="utf-8")
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for content in [markdown, html]:
        assert "Live apply planning" in content
        assert "deploy_live_apply_plan_record" in content
        assert "plan-only" in content
        assert "Run performed" in content
        assert "Mutated cluster" in content
        assert "Live apply allowed" in content
        assert "Future approval required" in content
