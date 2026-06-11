from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


REQUIRED_ARTIFACTS = {
    "node_profile",
    "node_inventory_record",
    "immutable_update_readiness_record",
    "agent_corps_plan",
    "deploy_plan",
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
    "summary",
}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_run_fogstack_local_demo_deploy_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "deploy"
    proc = subprocess.run(
        [sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(output_dir), "--summary"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack local demo deploy plan passed." in proc.stdout
    assert "Live cluster preflight record:" in proc.stdout
    assert "Checks passed: 16" in proc.stdout

    summary_path = output_dir / "fogstack.access.deploy-demo.summary.json"
    summary = load(summary_path)
    assert summary["kind"] == "FogStackLocalDemoDeployPlanRun"
    assert summary["bundle_id"] == "fogstack.access"
    assert summary["version"] == "0.1.0"
    assert summary["target"] == "kubernetes"
    assert REQUIRED_ARTIFACTS == set(summary["artifacts"])
    assert "live_cluster_preflight_record_emitted" in summary["checks"]

    for ref in summary["artifacts"].values():
        assert Path(ref).exists(), ref

    node_profile = load(Path(summary["artifacts"]["node_profile"]))
    surfaces = {surface["id"]: surface for surface in node_profile["use_surfaces"]}
    assert surfaces["turtleterm"]["repo_ref"] == "github://SourceOS-Linux/TurtleTerm"
    assert surfaces["bearbrowser"]["repo_ref"] == "github://SourceOS-Linux/BearBrowser"

    node_inventory = load(Path(summary["artifacts"]["node_inventory_record"]))
    assert node_inventory["kind"] == "FogStackAgentMachineNodeInventoryRecord"
    assert node_inventory["status"] == "passed"
    assert node_inventory["storage"]["topolvm_required"] is True
    assert node_inventory["cluster"]["join_policy"] == "approval-required"

    immutable_update = load(Path(summary["artifacts"]["immutable_update_readiness_record"]))
    assert immutable_update["kind"] == "FogStackImmutableUpdateReadinessRecord"
    assert immutable_update["status"] == "passed"
    assert immutable_update["policy"]["live_update_allowed"] is False

    cluster_readiness = load(Path(summary["artifacts"]["cluster_readiness_record"]))
    assert cluster_readiness["kind"] == "FogStackClusterReadinessRecord"
    assert cluster_readiness["status"] == "passed"

    gitops_readiness = load(Path(summary["artifacts"]["gitops_readiness_record"]))
    assert gitops_readiness["kind"] == "FogStackGitOpsReadinessRecord"
    assert gitops_readiness["status"] == "passed"

    live_preflight = load(Path(summary["artifacts"]["live_cluster_preflight_record"]))
    assert live_preflight["kind"] == "FogStackLiveClusterPreflightRecord"
    assert live_preflight["status"] == "blocked"
    assert live_preflight["mode"] == "read-only-live-preflight"
    assert live_preflight["safety"]["mutated_cluster"] is False
    assert live_preflight["safety"]["live_apply_allowed"] is False
    assert live_preflight["safety"]["human_approval_required_for_apply"] is True

    runtime_adapter = load(Path(summary["artifacts"]["runtime_adapter"]))
    assert runtime_adapter["kind"] == "FogStackLocalClusterRuntimeAdapter"
    assert runtime_adapter["runtime_policy"]["live_apply_allowed"] is False
    assert runtime_adapter["inputs"]["node_profile_digest"].startswith("sha256:")

    runtime_dry_run = load(Path(summary["artifacts"]["runtime_dry_run_record"]))
    assert runtime_dry_run["kind"] == "FogStackRuntimeDryRunRecord"
    assert runtime_dry_run["dry_run_result"]["mutated_cluster"] is False
    assert "node_profile" in runtime_dry_run["dry_run_result"]["validated_inputs"]

    deployment = yaml.safe_load(Path(summary["artifacts"]["kubernetes_deployment"]).read_text(encoding="utf-8"))
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["labels"]["fogstack.socioprophet.io/agent-corps"] == "enabled"
