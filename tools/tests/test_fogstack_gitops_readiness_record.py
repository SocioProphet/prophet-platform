from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")


def build_bundle(tmp_path: Path) -> Path:
    contract = tmp_path / "runtime-contract.json"
    deploy_plan = tmp_path / "deploy-plan.json"
    manifest_dir = tmp_path / "manifests"
    output_dir = tmp_path / "gitops"
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(deploy_plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--output-dir", str(manifest_dir)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_gitops_bundle.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifest_dir), "--output-dir", str(output_dir)], check=True)
    subprocess.run([sys.executable, "tools/check_fogstack_gitops_bundle.py", "--bundle", str(output_dir / "gitops-bundle.json")], check=True)
    return output_dir / "gitops-bundle.json"


def test_emit_fogstack_gitops_readiness_record_passed(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    output = tmp_path / "gitops-readiness.record.json"
    subprocess.run([sys.executable, "tools/emit_fogstack_gitops_readiness_record.py", "--bundle", str(bundle), "--output", str(output)], check=True)
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["kind"] == "FogStackGitOpsReadinessRecord"
    assert record["status"] == "passed"
    assert record["bundle_id"] == "fogstack.access"
    assert record["version"] == "0.1.0"
    assert record["source"]["target_revision"] == "main"
    assert record["gitops_bundle_digest"].startswith("sha256:")
    assert record["generator"]["status"] == "passed"
    assert record["checker"]["status"] == "passed"
    assert record["validation_result"]["bundle_validated"] is True


def test_emit_fogstack_gitops_readiness_record_failed_checker(tmp_path: Path) -> None:
    bundle = build_bundle(tmp_path)
    output = tmp_path / "gitops-readiness.record.json"
    proc = subprocess.run([sys.executable, "tools/emit_fogstack_gitops_readiness_record.py", "--bundle", str(bundle), "--output", str(output), "--checker-status", "failed", "--checker-message", "forced failure"], capture_output=True, text=True)
    assert proc.returncode != 0
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert record["checker"]["status"] == "failed"
    assert record["checker"]["message"] == "forced failure"
    assert record["validation_result"]["bundle_validated"] is False
