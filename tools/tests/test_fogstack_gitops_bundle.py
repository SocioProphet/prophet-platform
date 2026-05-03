from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/gitops/fogstack-gitops-bundle-v0.1.schema.json")
MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_build_fogstack_gitops_bundle(tmp_path: Path) -> None:
    contract = tmp_path / "runtime-contract.json"
    deploy_plan = tmp_path / "deploy-plan.json"
    manifest_dir = tmp_path / "manifests"
    output_dir = tmp_path / "gitops"

    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(deploy_plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--output-dir", str(manifest_dir)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_gitops_bundle.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifest_dir), "--output-dir", str(output_dir), "--repo-url", "https://example.invalid/repo.git", "--target-revision", "main", "--gitops-path", "gitops/fogstack.access"], check=True)

    bundle = load_json(output_dir / "gitops-bundle.json")
    Draft202012Validator(load_json(SCHEMA)).validate(bundle)
    assert bundle["kind"] == "FogStackGitOpsBundle"
    assert bundle["bundle_id"] == "fogstack.access"
    assert bundle["version"] == "0.1.0"
    assert bundle["namespace"] == "fogstack-access"
    assert bundle["deploy_plan_digest"].startswith("sha256:")
    assert bundle["agent_corps_plan_digest"].startswith("sha256:")

    application = load_yaml(output_dir / "application.yaml")
    assert application["kind"] == "Application"
    assert application["metadata"]["name"] == "fogstack-access"
    assert application["spec"]["source"]["path"] == "gitops/fogstack.access"
    assert application["spec"]["destination"]["namespace"] == "fogstack-access"

    kustomization = load_yaml(output_dir / "kustomization.yaml")
    assert kustomization["kind"] == "Kustomization"
    assert kustomization["resources"] == ["manifests/configmap.yaml", "manifests/deployment.yaml", "manifests/service.yaml"]

    artifact_ids = {artifact["id"] for artifact in bundle["artifacts"]}
    assert {"deploy-plan", "agent-corps-plan", "application", "kustomization", "configmap", "deployment", "service"}.issubset(artifact_ids)
    for artifact in bundle["artifacts"]:
        assert artifact["digest"].startswith("sha256:")
        assert Path(artifact["ref"]).exists(), artifact
