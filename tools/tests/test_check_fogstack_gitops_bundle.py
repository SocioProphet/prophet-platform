from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")


def build_bundle(tmp_path: Path) -> Path:
    contract = tmp_path / "runtime-contract.json"
    deploy_plan = tmp_path / "deploy-plan.json"
    manifest_dir = tmp_path / "manifests"
    output_dir = tmp_path / "gitops"
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(deploy_plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--output-dir", str(manifest_dir)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_gitops_bundle.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifest_dir), "--output-dir", str(output_dir), "--repo-url", "https://example.invalid/repo.git", "--target-revision", "main", "--gitops-path", "gitops/fogstack.access"], check=True)
    return output_dir / "gitops-bundle.json"


def run_checker(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "tools/check_fogstack_gitops_bundle.py", "--bundle", str(bundle)], capture_output=True, text=True)


def test_check_fogstack_gitops_bundle_passes(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    proc = run_checker(bundle)
    assert proc.returncode == 0
    assert "FogStack GitOps bundle passed." in proc.stdout


def test_check_fogstack_gitops_bundle_rejects_bad_application_digest(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    data = json.loads(bundle.read_text(encoding="utf-8"))
    data["application"]["digest"] = "sha256:" + ("0" * 64)
    data["artifacts"] = [artifact if artifact["id"] != "application" else {**artifact, "digest": data["application"]["digest"]} for artifact in data["artifacts"]]
    bundle.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    proc = run_checker(bundle)
    assert proc.returncode != 0
    assert "artifact digest mismatch: application" in proc.stderr


def test_check_fogstack_gitops_bundle_rejects_application_path_mismatch(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    data = json.loads(bundle.read_text(encoding="utf-8"))
    application_path = Path(data["application"]["ref"])
    application = yaml.safe_load(application_path.read_text(encoding="utf-8"))
    application["spec"]["source"]["path"] = "wrong/path"
    application_path.write_text(yaml.safe_dump(application, sort_keys=False), encoding="utf-8")
    proc = run_checker(bundle)
    assert proc.returncode != 0
    assert "Application path mismatch" in proc.stderr
