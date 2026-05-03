from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")


def build_inputs(tmp_path: Path) -> tuple[Path, Path]:
    contract = tmp_path / "runtime-contract.json"
    plan = tmp_path / "deploy-plan.json"
    manifest_dir = tmp_path / "manifests"
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(plan), "--output-dir", str(manifest_dir)], check=True)
    return plan, manifest_dir


def run_checker(plan: Path, manifest_dir: Path, record: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "tools/check_fogstack_kubernetes_manifests.py", "--deploy-plan", str(plan), "--manifest-dir", str(manifest_dir), "--record-output", str(record), *extra], capture_output=True, text=True)


def read_record(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_cluster_readiness_record_offline(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    record_path = tmp_path / "readiness.json"
    proc = run_checker(plan, manifest_dir, record_path)
    assert proc.returncode == 0
    record = read_record(record_path)
    assert record["kind"] == "FogStackClusterReadinessRecord"
    assert record["status"] == "passed"
    assert record["validation_path"] == "offline"
    assert record["offline_validation"]["status"] == "passed"
    assert record["kubectl"]["dry_run_status"] == "not_requested"


def test_cluster_readiness_record_kubectl_fallback(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    record_path = tmp_path / "readiness.json"
    proc = run_checker(plan, manifest_dir, record_path, "--kubectl-dry-run", "--kubectl", "missing-kubectl-for-test")
    assert proc.returncode == 0
    record = read_record(record_path)
    assert record["validation_path"] == "offline-fallback"
    assert record["kubectl"]["dry_run_status"] == "fallback"
    assert record["kubectl"]["fallback_mode"] == "offline_validation"


def test_cluster_readiness_record_kubectl_success(tmp_path: Path) -> None:
    plan, manifest_dir = build_inputs(tmp_path)
    record_path = tmp_path / "readiness.json"
    kubectl = tmp_path / "kubectl"
    kubectl.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    kubectl.chmod(kubectl.stat().st_mode | 0o111)
    proc = run_checker(plan, manifest_dir, record_path, "--kubectl-dry-run", "--kubectl", str(kubectl))
    assert proc.returncode == 0
    record = read_record(record_path)
    assert record["validation_path"] == "offline+kubectl-dry-run"
    assert record["kubectl"]["dry_run_status"] == "passed"
