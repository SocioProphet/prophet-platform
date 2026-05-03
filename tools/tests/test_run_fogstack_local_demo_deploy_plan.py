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
    assert "Checks passed: 6" in proc.stdout

    summary_path = output_dir / "fogstack.access.deploy-demo.summary.json"
    check_record_path = output_dir / "fogstack.access.kubernetes-manifest-check.record.json"
    runtime_contract_path = output_dir / "fogstack.access.runtime-contract.json"
    deploy_plan_path = output_dir / "fogstack.access.deploy-plan.json"
    manifest_dir = output_dir / "kubernetes"

    for path in [
        summary_path,
        check_record_path,
        runtime_contract_path,
        deploy_plan_path,
        manifest_dir / "configmap.yaml",
        manifest_dir / "deployment.yaml",
        manifest_dir / "service.yaml",
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
    }

    artifacts = summary["artifacts"]
    assert artifacts["agent_corps_plan"].endswith("fogstack.access.runtime-contract.json")
    assert artifacts["deploy_plan"].endswith("fogstack.access.deploy-plan.json")
    assert artifacts["kubernetes_configmap"].endswith("configmap.yaml")
    assert artifacts["kubernetes_deployment"].endswith("deployment.yaml")
    assert artifacts["kubernetes_service"].endswith("service.yaml")
    assert artifacts["kubernetes_manifest_check_record"].endswith("fogstack.access.kubernetes-manifest-check.record.json")

    check_record = json.loads(check_record_path.read_text(encoding="utf-8"))
    assert check_record["kind"] == "FogStackKubernetesManifestCheckRecord"
    assert check_record["status"] == "passed"
    assert check_record["bundle_id"] == "fogstack.access"
    assert "FogStack Kubernetes manifests passed." in check_record["checker_stdout"]

    deployment = yaml.safe_load((manifest_dir / "deployment.yaml").read_text(encoding="utf-8"))
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["labels"]["fogstack.socioprophet.io/agent-corps"] == "enabled"
