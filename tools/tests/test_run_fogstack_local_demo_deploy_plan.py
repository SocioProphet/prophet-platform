from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


def test_run_fogstack_local_demo_deploy_plan(tmp_path: Path) -> None:
    output_dir = tmp_path / "deploy"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_fogstack_local_demo_deploy_plan.py",
            "--output-dir",
            str(output_dir),
            "--summary",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FogStack local demo deploy plan passed." in proc.stdout
    assert "Bundle: fogstack.access@0.1.0" in proc.stdout
    assert "Target: kubernetes" in proc.stdout
    assert "Cluster readiness record:" in proc.stdout
    assert "GitOps bundle:" in proc.stdout
    assert "GitOps application:" in proc.stdout
    assert "GitOps readiness record:" in proc.stdout
    assert "Checks passed: 10" in proc.stdout

    summary_path = output_dir / "fogstack.access.deploy-demo.summary.json"
    check_record_path = output_dir / "fogstack.access.kubernetes-manifest-check.record.json"
    readiness_record_path = output_dir / "fogstack.access.cluster-readiness.record.json"
    gitops_readiness_path = output_dir / "fogstack.access.gitops-readiness.record.json"
    runtime_contract_path = output_dir / "fogstack.access.runtime-contract.json"
    deploy_plan_path = output_dir / "fogstack.access.deploy-plan.json"
    manifest_dir = output_dir / "kubernetes"
    gitops_dir = output_dir / "gitops"

    for path in [
        summary_path,
        check_record_path,
        readiness_record_path,
        gitops_readiness_path,
        runtime_contract_path,
        deploy_plan_path,
        manifest_dir / "configmap.yaml",
        manifest_dir / "deployment.yaml",
        manifest_dir / "service.yaml",
        gitops_dir / "gitops-bundle.json",
        gitops_dir / "application.yaml",
        gitops_dir / "kustomization.yaml",
        gitops_dir / "manifests" / "configmap.yaml",
        gitops_dir / "manifests" / "deployment.yaml",
        gitops_dir / "manifests" / "service.yaml",
    ]:
        assert path.exists(), f"missing {path}"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["kind"] == "FogStackLocalDemoDeployPlanRun"
    assert summary["bundle_id"] == "fogstack.access"
    assert summary["version"] == "0.1.0"
    assert summary["target"] == "kubernetes"
    assert set(summary["checks"]) == {
        "agent_corps_plan_built",
        "agent_corps_plan_checked",
        "deploy_plan_built",
        "deploy_plan_checked",
        "kubernetes_manifests_rendered",
        "kubernetes_manifests_checked",
        "cluster_readiness_record_emitted",
        "gitops_bundle_built",
        "gitops_bundle_checked",
        "gitops_readiness_record_emitted",
    }

    artifacts = summary["artifacts"]
    assert artifacts["agent_corps_plan"].endswith("fogstack.access.runtime-contract.json")
    assert artifacts["deploy_plan"].endswith("fogstack.access.deploy-plan.json")
    assert artifacts["kubernetes_configmap"].endswith("configmap.yaml")
    assert artifacts["kubernetes_deployment"].endswith("deployment.yaml")
    assert artifacts["kubernetes_service"].endswith("service.yaml")
    assert artifacts["kubernetes_manifest_check_record"].endswith("fogstack.access.kubernetes-manifest-check.record.json")
    assert artifacts["cluster_readiness_record"].endswith("fogstack.access.cluster-readiness.record.json")
    assert artifacts["gitops_bundle"].endswith("gitops-bundle.json")
    assert artifacts["gitops_application"].endswith("application.yaml")
    assert artifacts["gitops_kustomization"].endswith("kustomization.yaml")
    assert artifacts["gitops_deployment"].endswith("deployment.yaml")
    assert artifacts["gitops_readiness_record"].endswith("fogstack.access.gitops-readiness.record.json")

    check_record = json.loads(check_record_path.read_text(encoding="utf-8"))
    assert check_record["kind"] == "FogStackKubernetesManifestCheckRecord"
    assert check_record["status"] == "passed"
    assert check_record["bundle_id"] == "fogstack.access"
    assert check_record["cluster_readiness_record_ref"].endswith("fogstack.access.cluster-readiness.record.json")
    assert "FogStack Kubernetes manifests passed." in check_record["checker_stdout"]

    readiness_record = json.loads(readiness_record_path.read_text(encoding="utf-8"))
    assert readiness_record["kind"] == "FogStackClusterReadinessRecord"
    assert readiness_record["status"] == "passed"
    assert readiness_record["offline_validation"]["status"] == "passed"

    gitops_bundle = json.loads((gitops_dir / "gitops-bundle.json").read_text(encoding="utf-8"))
    assert gitops_bundle["kind"] == "FogStackGitOpsBundle"
    assert gitops_bundle["bundle_id"] == "fogstack.access"
    assert gitops_bundle["deploy_plan_digest"].startswith("sha256:")

    gitops_readiness = json.loads(gitops_readiness_path.read_text(encoding="utf-8"))
    assert gitops_readiness["kind"] == "FogStackGitOpsReadinessRecord"
    assert gitops_readiness["status"] == "passed"
    assert gitops_readiness["validation_result"]["bundle_validated"] is True

    deployment = yaml.safe_load((manifest_dir / "deployment.yaml").read_text(encoding="utf-8"))
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["labels"]["fogstack.socioprophet.io/agent-corps"] == "enabled"
