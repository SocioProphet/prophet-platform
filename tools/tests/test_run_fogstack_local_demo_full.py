from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED_FULL_ARTIFACTS = {
    "local_demo_summary",
    "local_demo_markdown",
    "local_demo_html",
    "artifact_index",
    "deploy_summary",
    "node_inventory_record",
    "immutable_update_readiness_record",
    "deploy_plan",
    "agent_corps_plan",
    "kubernetes_configmap",
    "kubernetes_deployment",
    "kubernetes_service",
    "kubernetes_manifest_check_record",
    "cluster_readiness_record",
    "gitops_bundle",
    "gitops_application",
    "gitops_kustomization",
    "gitops_configmap",
    "gitops_deployment",
    "gitops_service",
    "gitops_readiness_record",
    "live_cluster_preflight_record",
    "runtime_adapter",
    "runtime_dry_run_record",
}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_run_fogstack_local_demo_full(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    proc = subprocess.run(
        [sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack full local demo passed." in proc.stdout
    assert "Live cluster preflight record:" in proc.stdout
    assert "Checks passed: 12" in proc.stdout

    full_summary_path = output_dir / "fogstack-local-demo.full.summary.json"
    full_summary = load(full_summary_path)
    assert full_summary["kind"] == "FogStackLocalDemoFullRun"
    assert full_summary["status"] == "passed"
    assert REQUIRED_FULL_ARTIFACTS == set(full_summary["artifacts"])
    assert "live_cluster_preflight_record_indexed" in full_summary["checks"]
    for ref in full_summary["artifacts"].values():
        assert Path(ref).exists(), ref

    live_preflight = load(Path(full_summary["artifacts"]["live_cluster_preflight_record"]))
    assert live_preflight["kind"] == "FogStackLiveClusterPreflightRecord"
    assert live_preflight["status"] == "blocked"
    assert live_preflight["mode"] == "read-only-live-preflight"
    assert live_preflight["safety"]["mutated_cluster"] is False
    assert live_preflight["safety"]["live_apply_allowed"] is False
    assert live_preflight["safety"]["human_approval_required_for_apply"] is True

    runtime_dry_run = load(Path(full_summary["artifacts"]["runtime_dry_run_record"]))
    assert runtime_dry_run["kind"] == "FogStackRuntimeDryRunRecord"
    assert runtime_dry_run["agentplane_run"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert runtime_dry_run["policyplane_decision"]["policyplane_ref"] == "github://SocioProphet/policy-fabric"
    assert runtime_dry_run["dry_run_result"]["mutated_cluster"] is False

    artifact_index = load(output_dir / "demo-artifacts.index.json")
    indexed_ids = {entry["id"] for entry in artifact_index["artifacts"]}
    assert "deploy_live_cluster_preflight_record" in indexed_ids
    assert "deploy_runtime_dry_run_record" in indexed_ids

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Deploy readiness" in html
    assert "Live cluster preflight" in html
    assert "deploy_live_cluster_preflight_record" in html
    assert "read-only-live-preflight" in html
    assert "Runtime evidence" in html
    assert "AgentPlane run ID" in html
    assert "PolicyPlane decision ID" in html
    assert "SHA-256 digest" in html
