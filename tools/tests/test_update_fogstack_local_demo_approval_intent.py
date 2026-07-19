from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_update_fogstack_local_demo_approval_intent(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    deploy_dir = output_dir / "deploy"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo.py", "--pack", "all", "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(deploy_dir)], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_deploy_artifacts.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--deploy-summary-json", str(deploy_dir / "fogstack.access.deploy-demo.summary.json")], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_apply_plan.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json")], check=True)
    proc = subprocess.run([sys.executable, "tools/update_fogstack_local_demo_approval_intent.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json")], check=True, capture_output=True, text=True)
    assert "FogStackLocalDemoApprovalIntentUpdate" in proc.stdout

    summary = load(output_dir / "fogstack-local-demo.summary.json")
    assert "deploy_approval_intent_record" in summary["artifacts"]
    assert "approval_intent_record_emitted" in summary["checks"]
    assert "approval_intent_record_indexed" in summary["checks"]
    assert "approval_intent_summary_appended" in summary["checks"]

    intent = load(Path(summary["artifacts"]["deploy_approval_intent_record"]))
    assert intent["kind"] == "FogStackApprovalIntentRecord"
    assert intent["mode"] == "intent-only"
    assert intent["status"] == "recorded"
    assert intent["safety"]["intent_only"] is True
    assert intent["safety"]["authorizes_execution"] is False
    assert intent["safety"]["run_performed"] is False
    assert intent["safety"]["mutated_cluster"] is False
    assert intent["safety"]["live_apply_allowed"] is False
    assert intent["safety"]["requires_policyplane_execute_decision"] is True
    assert intent["safety"]["requires_agentplane_execution_run"] is True
    assert intent["safety"]["requires_rollback_plan"] is True
    assert intent["safety"]["requires_external_identity_binding"] is True

    index = load(output_dir / "demo-artifacts.index.json")
    indexed = {entry["id"]: entry for entry in index["artifacts"]}
    assert "deploy_approval_intent_record" in indexed
    assert indexed["deploy_approval_intent_record"]["digest"].startswith("sha256:")
    assert Path(indexed["deploy_approval_intent_record"]["ref"]).exists()

    markdown = (output_dir / "fogstack-local-demo.summary.md").read_text(encoding="utf-8")
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for content in [markdown, html]:
        assert "Approval intent" in content
        assert "deploy_approval_intent_record" in content
        assert "intent-only" in content
        assert "Authorizes execution" in content
        assert "Run performed" in content
        assert "Mutated cluster" in content
        assert "Live apply allowed" in content
        assert "Requires PolicyPlane execute decision" in content
        assert "Requires AgentPlane execution run" in content
