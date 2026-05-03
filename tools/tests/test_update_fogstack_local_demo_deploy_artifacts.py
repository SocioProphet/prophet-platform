from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED = {
    "deploy_node_profile",
    "deploy_node_inventory_record",
    "deploy_immutable_update_readiness_record",
    "deploy_agent_corps_plan",
    "deploy_plan",
    "deploy_kubernetes_configmap",
    "deploy_kubernetes_deployment",
    "deploy_kubernetes_service",
    "deploy_kubernetes_manifest_check_record",
    "deploy_cluster_readiness_record",
    "deploy_gitops_bundle",
    "deploy_gitops_application",
    "deploy_gitops_kustomization",
    "deploy_gitops_configmap",
    "deploy_gitops_deployment",
    "deploy_gitops_service",
    "deploy_gitops_readiness_record",
    "deploy_live_cluster_preflight_record",
    "deploy_runtime_adapter",
    "deploy_runtime_dry_run_record",
    "deploy_summary",
}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_update_fogstack_local_demo_deploy_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    deploy_dir = output_dir / "deploy"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo.py", "--pack", "all", "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(deploy_dir)], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_deploy_artifacts.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--deploy-summary-json", str(deploy_dir / "fogstack.access.deploy-demo.summary.json")], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_gitops_readiness.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--gitops-readiness-record", str(deploy_dir / "fogstack.access.gitops-readiness.record.json")], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_runtime_evidence.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--runtime-adapter", str(deploy_dir / "fogstack.access.local-cluster-runtime-adapter.json"), "--runtime-dry-run-record", str(deploy_dir / "fogstack.access.runtime-dry-run.record.json")], check=True)

    summary = load(output_dir / "fogstack-local-demo.summary.json")
    assert REQUIRED.issubset(set(summary["artifacts"]))
    assert "live_cluster_preflight_record_emitted" in summary["checks"]
    assert "gitops_readiness_record_indexed" in summary["checks"]
    assert "runtime_adapter_indexed" in summary["checks"]
    assert "runtime_dry_run_record_indexed" in summary["checks"]

    artifact_index = load(output_dir / "demo-artifacts.index.json")
    indexed = {entry["id"]: entry for entry in artifact_index["artifacts"]}
    assert REQUIRED.issubset(set(indexed))
    assert indexed["deploy_live_cluster_preflight_record"]["digest"].startswith("sha256:")
    assert Path(indexed["deploy_live_cluster_preflight_record"]["ref"]).exists()

    live_preflight = load(Path(summary["artifacts"]["deploy_live_cluster_preflight_record"]))
    assert live_preflight["kind"] == "FogStackLiveClusterPreflightRecord"
    assert live_preflight["status"] == "blocked"
    assert live_preflight["mode"] == "read-only-live-preflight"
    assert live_preflight["safety"]["mutated_cluster"] is False
    assert live_preflight["safety"]["live_apply_allowed"] is False
    assert live_preflight["safety"]["human_approval_required_for_apply"] is True

    runtime_dry_run = load(Path(summary["artifacts"]["deploy_runtime_dry_run_record"]))
    assert runtime_dry_run["kind"] == "FogStackRuntimeDryRunRecord"
    assert runtime_dry_run["dry_run_result"]["mutated_cluster"] is False
    assert "node_profile" in runtime_dry_run["dry_run_result"]["validated_inputs"]

    markdown = (output_dir / "fogstack-local-demo.summary.md").read_text(encoding="utf-8")
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for content in [markdown, html]:
        assert "Live cluster preflight" in content
        assert "deploy_live_cluster_preflight_record" in content
        assert "read-only-live-preflight" in content
        assert "Runtime evidence" in content
        assert "SHA-256 digest" in content
