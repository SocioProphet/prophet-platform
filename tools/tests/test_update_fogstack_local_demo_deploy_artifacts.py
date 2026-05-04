from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED = {
    "deploy_node_profile",
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
    "deploy_runtime_adapter",
    "deploy_runtime_dry_run_record",
    "deploy_summary",
}


def test_update_fogstack_local_demo_deploy_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    deploy_dir = output_dir / "deploy"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo.py", "--pack", "all", "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(deploy_dir)], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_deploy_artifacts.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--deploy-summary-json", str(deploy_dir / "fogstack.access.deploy-demo.summary.json")], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_gitops_readiness.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--gitops-readiness-record", str(deploy_dir / "fogstack.access.gitops-readiness.record.json")], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_runtime_evidence.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--runtime-adapter", str(deploy_dir / "fogstack.access.local-cluster-runtime-adapter.json"), "--runtime-dry-run-record", str(deploy_dir / "fogstack.access.runtime-dry-run.record.json")], check=True)

    summary = json.loads((output_dir / "fogstack-local-demo.summary.json").read_text(encoding="utf-8"))
    assert REQUIRED.issubset(set(summary["artifacts"]))
    assert "node_profile_built" in summary["checks"]
    assert "deploy_plan_built" in summary["checks"]
    assert "kubernetes_manifests_checked" in summary["checks"]
    assert "cluster_readiness_record_emitted" in summary["checks"]
    assert "gitops_bundle_built" in summary["checks"]
    assert "gitops_bundle_checked" in summary["checks"]
    assert "gitops_readiness_record_indexed" in summary["checks"]
    assert "runtime_adapter_indexed" in summary["checks"]
    assert "runtime_dry_run_record_indexed" in summary["checks"]
    assert "runtime_readiness_summary_appended" in summary["checks"]
    assert "agentplane_run_linked" in summary["checks"]

    artifact_index = json.loads((output_dir / "demo-artifacts.index.json").read_text(encoding="utf-8"))
    indexed = {entry["id"]: entry for entry in artifact_index["artifacts"]}
    assert REQUIRED.issubset(set(indexed))
    for key in REQUIRED:
        assert indexed[key]["digest"].startswith("sha256:")
        assert Path(indexed[key]["ref"]).exists()

    node_profile = json.loads(Path(summary["artifacts"]["deploy_node_profile"]).read_text(encoding="utf-8"))
    assert node_profile["kind"] == "FogStackAgentMachineNodeProfile"
    surfaces = {surface["id"]: surface for surface in node_profile["use_surfaces"]}
    assert surfaces["turtleterm"]["repo_ref"] == "github://SourceOS-Linux/TurtleTerm"
    assert surfaces["bearbrowser"]["repo_ref"] == "github://SourceOS-Linux/BearBrowser"

    readiness_record = json.loads(Path(summary["artifacts"]["deploy_cluster_readiness_record"]).read_text(encoding="utf-8"))
    assert readiness_record["kind"] == "FogStackClusterReadinessRecord"
    assert readiness_record["status"] == "passed"

    gitops_bundle = json.loads(Path(summary["artifacts"]["deploy_gitops_bundle"]).read_text(encoding="utf-8"))
    assert gitops_bundle["kind"] == "FogStackGitOpsBundle"
    assert gitops_bundle["bundle_id"] == "fogstack.access"

    gitops_readiness = json.loads(Path(summary["artifacts"]["deploy_gitops_readiness_record"]).read_text(encoding="utf-8"))
    assert gitops_readiness["kind"] == "FogStackGitOpsReadinessRecord"
    assert gitops_readiness["status"] == "passed"

    runtime_adapter = json.loads(Path(summary["artifacts"]["deploy_runtime_adapter"]).read_text(encoding="utf-8"))
    assert runtime_adapter["kind"] == "FogStackLocalClusterRuntimeAdapter"
    assert runtime_adapter["runtime_policy"]["live_apply_allowed"] is False
    assert runtime_adapter["inputs"]["node_profile_digest"].startswith("sha256:")

    runtime_dry_run = json.loads(Path(summary["artifacts"]["deploy_runtime_dry_run_record"]).read_text(encoding="utf-8"))
    assert runtime_dry_run["kind"] == "FogStackRuntimeDryRunRecord"
    assert runtime_dry_run["agentplane_run"]["run_id"] == "agentplane-run:fogstack.access:local-dry-run"
    assert runtime_dry_run["agentplane_run"]["run_ref"] == "agentplane://runs/fogstack.access/local-dry-run"
    assert runtime_dry_run["agentplane_run"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert runtime_dry_run["agentplane_run"]["requested_by"] == "human:operator"
    assert runtime_dry_run["agentplane_run"]["approval_state"] == "live-apply-requires-human-approval"
    assert runtime_dry_run["dry_run_result"]["mutated_cluster"] is False
    assert runtime_dry_run["dry_run_result"]["validation_path"] == "contract-and-digest-only"
    assert "agentplane_run" in runtime_dry_run["dry_run_result"]["validated_inputs"]
    assert "node_profile" in runtime_dry_run["dry_run_result"]["validated_inputs"]

    markdown = (output_dir / "fogstack-local-demo.summary.md").read_text(encoding="utf-8")
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for content in [markdown, html]:
        assert "Deploy readiness" in content
        assert "GitOps readiness" in content
        assert "Runtime evidence" in content
        assert "Runtime readiness" in content
        assert "AgentPlane run ID" in content
        assert "agentplane-run:fogstack.access:local-dry-run" in content
        assert "agentplane://runs/fogstack.access/local-dry-run" in content
        assert "github://SocioProphet/agentplane" in content
        assert "live-apply-requires-human-approval" in content
        assert "TurtleTerm" in content
        assert "BearBrowser" in content
        assert "github://SourceOS-Linux/TurtleTerm" in content
        assert "github://SourceOS-Linux/BearBrowser" in content
        assert "contract-and-digest-only" in content
        assert "Mutated cluster" in content
        assert "Live apply allowed" in content
        assert "Human approval required" in content
        assert "Artifact ID" in content
        assert "SHA-256 digest" in content
        assert "indexed" in content
        assert "deploy_node_profile" in content
        assert "deploy_plan" in content
        assert "deploy_kubernetes_deployment" in content
        assert "deploy_cluster_readiness_record" in content
        assert "deploy_gitops_bundle" in content
        assert "deploy_gitops_application" in content
        assert "deploy_gitops_readiness_record" in content
        assert "deploy_runtime_adapter" in content
        assert "deploy_runtime_dry_run_record" in content
        assert "sha256:" in content
