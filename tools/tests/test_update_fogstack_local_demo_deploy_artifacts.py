from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REQUIRED = {
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
    "deploy_summary",
}


def test_update_fogstack_local_demo_deploy_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"
    deploy_dir = output_dir / "deploy"
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo.py", "--pack", "all", "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/run_fogstack_local_demo_deploy_plan.py", "--output-dir", str(deploy_dir)], check=True)
    subprocess.run([sys.executable, "tools/update_fogstack_local_demo_deploy_artifacts.py", "--summary-json", str(output_dir / "fogstack-local-demo.summary.json"), "--deploy-summary-json", str(deploy_dir / "fogstack.access.deploy-demo.summary.json")], check=True)

    summary = json.loads((output_dir / "fogstack-local-demo.summary.json").read_text(encoding="utf-8"))
    assert REQUIRED.issubset(set(summary["artifacts"]))
    assert "deploy_plan_built" in summary["checks"]
    assert "kubernetes_manifests_checked" in summary["checks"]
    assert "cluster_readiness_record_emitted" in summary["checks"]
    assert "gitops_bundle_built" in summary["checks"]
    assert "gitops_bundle_checked" in summary["checks"]

    artifact_index = json.loads((output_dir / "demo-artifacts.index.json").read_text(encoding="utf-8"))
    indexed = {entry["id"]: entry for entry in artifact_index["artifacts"]}
    assert REQUIRED.issubset(set(indexed))
    for key in REQUIRED:
        assert indexed[key]["digest"].startswith("sha256:")
        assert Path(indexed[key]["ref"]).exists()

    readiness_record = json.loads(Path(summary["artifacts"]["deploy_cluster_readiness_record"]).read_text(encoding="utf-8"))
    assert readiness_record["kind"] == "FogStackClusterReadinessRecord"
    assert readiness_record["status"] == "passed"

    gitops_bundle = json.loads(Path(summary["artifacts"]["deploy_gitops_bundle"]).read_text(encoding="utf-8"))
    assert gitops_bundle["kind"] == "FogStackGitOpsBundle"
    assert gitops_bundle["bundle_id"] == "fogstack.access"

    markdown = (output_dir / "fogstack-local-demo.summary.md").read_text(encoding="utf-8")
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for content in [markdown, html]:
        assert "Deploy readiness" in content
        assert "Artifact ID" in content
        assert "SHA-256 digest" in content
        assert "indexed" in content
        assert "deploy_plan" in content
        assert "deploy_kubernetes_deployment" in content
        assert "deploy_cluster_readiness_record" in content
        assert "deploy_gitops_bundle" in content
        assert "deploy_gitops_application" in content
        assert "sha256:" in content
