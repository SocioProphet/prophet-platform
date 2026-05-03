from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
LABEL = "fogstack.socioprophet.io/bundle-id"
CORPS = "fogstack.socioprophet.io/agent-corps"


def build_inputs(tmp_path: Path) -> tuple[Path, Path]:
    contract = tmp_path / "runtime-contract.json"
    plan = tmp_path / "deploy-plan.json"
    manifest_dir = tmp_path / "manifests"
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(plan), "--output-dir", str(manifest_dir)], check=True)
    return plan, manifest_dir


def run_checker(plan: Path, manifest_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "tools/check_fogstack_kubernetes_manifests.py", "--deploy-plan", str(plan), "--manifest-dir", str(manifest_dir), *extra], capture_output=True, text=True)


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_check_fogstack_kubernetes_manifests_passes(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    proc = run_checker(plan, manifest_dir)
    assert proc.returncode == 0
    assert "FogStack Kubernetes manifests passed." in proc.stdout
    assert "offline validation passed" in proc.stdout


def test_check_fogstack_kubernetes_manifests_kubectl_fallback(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    proc = run_checker(plan, manifest_dir, "--kubectl-dry-run", "--kubectl", "definitely-missing-kubectl")
    assert proc.returncode == 0
    assert "kubectl unavailable; offline validation used" in proc.stdout


def test_check_fogstack_kubernetes_manifests_requires_kubectl_when_requested(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    proc = run_checker(plan, manifest_dir, "--kubectl-dry-run", "--require-kubectl", "--kubectl", "definitely-missing-kubectl")
    assert proc.returncode != 0
    assert "kubectl not found" in proc.stderr


def test_check_fogstack_kubernetes_manifests_kubectl_success_path(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    fake_kubectl = tmp_path / "kubectl"
    fake_kubectl.write_text("#!/usr/bin/env sh\necho kubectl dry-run ok\nexit 0\n", encoding="utf-8")
    fake_kubectl.chmod(fake_kubectl.stat().st_mode | 0o111)
    proc = run_checker(plan, manifest_dir, "--kubectl-dry-run", "--kubectl", str(fake_kubectl))
    assert proc.returncode == 0
    assert "kubectl dry-run passed" in proc.stdout


def test_check_fogstack_kubernetes_manifests_rejects_missing_agent_corps_label(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    deployment = load_yaml(manifest_dir / "deployment.yaml")
    del deployment["metadata"]["labels"][CORPS]
    write_yaml(manifest_dir / "deployment.yaml", deployment)
    proc = run_checker(plan, manifest_dir)
    assert proc.returncode != 0
    assert f"deployment label mismatch: {CORPS}" in proc.stderr


def test_check_fogstack_kubernetes_manifests_rejects_bad_service_selector(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    service = load_yaml(manifest_dir / "service.yaml")
    service["spec"]["selector"][LABEL] = "fogstack.wrong"
    write_yaml(manifest_dir / "service.yaml", service)
    proc = run_checker(plan, manifest_dir)
    assert proc.returncode != 0
    assert "service selector mismatch" in proc.stderr
