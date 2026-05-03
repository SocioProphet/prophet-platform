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
    "runtime_adapter",
    "runtime_dry_run_record",
}


def test_run_fogstack_local_demo_full(tmp_path: Path) -> None:
    output_dir = tmp_path / "fogstack-local-demo"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo_full.py",
            "--output-dir",
            str(output_dir),
            "--summary",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack full local demo passed." in proc.stdout
    assert "Artifact index:" in proc.stdout
    assert "Deploy plan:" in proc.stdout
    assert "Kubernetes deployment:" in proc.stdout
    assert "Cluster readiness record:" in proc.stdout
    assert "GitOps bundle:" in proc.stdout
    assert "GitOps application:" in proc.stdout
    assert "GitOps readiness record:" in proc.stdout
    assert "Runtime adapter:" in proc.stdout
    assert "Runtime dry-run record:" in proc.stdout

    full_summary_path = output_dir / "fogstack-local-demo.full.summary.json"
    assert full_summary_path.exists()
    full_summary = json.loads(full_summary_path.read_text(encoding="utf-8"))
    assert full_summary["kind"] == "FogStackLocalDemoFullRun"
    assert full_summary["status"] == "passed"
    assert REQUIRED_FULL_ARTIFACTS == set(full_summary["artifacts"])
    assert "cluster_readiness_record_indexed" in full_summary["checks"]
    assert "gitops_bundle_indexed" in full_summary["checks"]
    assert "gitops_readiness_record_indexed" in full_summary["checks"]
    assert "runtime_adapter_indexed" in full_summary["checks"]
    assert "runtime_dry_run_record_indexed" in full_summary["checks"]
    for ref in full_summary["artifacts"].values():
        assert Path(ref).exists(), ref

    readiness_record = json.loads(Path(full_summary["artifacts"]["cluster_readiness_record"]).read_text(encoding="utf-8"))
    assert readiness_record["kind"] == "FogStackClusterReadinessRecord"
    assert readiness_record["status"] == "passed"

    gitops_bundle = json.loads(Path(full_summary["artifacts"]["gitops_bundle"]).read_text(encoding="utf-8"))
    assert gitops_bundle["kind"] == "FogStackGitOpsBundle"
    assert gitops_bundle["bundle_id"] == "fogstack.access"

    gitops_readiness = json.loads(Path(full_summary["artifacts"]["gitops_readiness_record"]).read_text(encoding="utf-8"))
    assert gitops_readiness["kind"] == "FogStackGitOpsReadinessRecord"
    assert gitops_readiness["status"] == "passed"

    runtime_adapter = json.loads(Path(full_summary["artifacts"]["runtime_adapter"]).read_text(encoding="utf-8"))
    assert runtime_adapter["kind"] == "FogStackLocalClusterRuntimeAdapter"
    assert runtime_adapter["runtime_policy"]["live_apply_allowed"] is False

    runtime_dry_run = json.loads(Path(full_summary["artifacts"]["runtime_dry_run_record"]).read_text(encoding="utf-8"))
    assert runtime_dry_run["kind"] == "FogStackRuntimeDryRunRecord"
    assert runtime_dry_run["dry_run_result"]["mutated_cluster"] is False

    artifact_index = json.loads((output_dir / "demo-artifacts.index.json").read_text(encoding="utf-8"))
    indexed_ids = {entry["id"] for entry in artifact_index["artifacts"]}
    assert "deploy_plan" in indexed_ids
    assert "deploy_kubernetes_deployment" in indexed_ids
    assert "deploy_kubernetes_manifest_check_record" in indexed_ids
    assert "deploy_cluster_readiness_record" in indexed_ids
    assert "deploy_gitops_bundle" in indexed_ids
    assert "deploy_gitops_application" in indexed_ids
    assert "deploy_gitops_deployment" in indexed_ids
    assert "deploy_gitops_readiness_record" in indexed_ids
    assert "deploy_runtime_adapter" in indexed_ids
    assert "deploy_runtime_dry_run_record" in indexed_ids

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Deploy readiness" in html
    assert "GitOps readiness" in html
    assert "Runtime evidence" in html
    assert "SHA-256 digest" in html
    assert "indexed" in html
    assert "deploy_plan" in html
    assert "deploy_cluster_readiness_record" in html
    assert "deploy_gitops_bundle" in html
    assert "deploy_gitops_readiness_record" in html
    assert "deploy_runtime_adapter" in html
    assert "deploy_runtime_dry_run_record" in html
    assert "fogstack.access.deploy-plan.json" in html
