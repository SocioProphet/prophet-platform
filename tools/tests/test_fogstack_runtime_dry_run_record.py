from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
SCHEMA = Path("schemas/runtime/fogstack-runtime-dry-run-record-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def build_inputs(tmp_path: Path) -> tuple[Path, Path]:
    contract = tmp_path / "runtime-contract.json"
    deploy_plan = tmp_path / "deploy-plan.json"
    manifests = tmp_path / "manifests"
    cluster_record = tmp_path / "cluster-readiness.json"
    gitops_dir = tmp_path / "gitops"
    gitops_record = tmp_path / "gitops-readiness.json"
    adapter = tmp_path / "runtime-adapter.json"
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(deploy_plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--output-dir", str(manifests)], check=True)
    subprocess.run([sys.executable, "tools/check_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifests), "--record-output", str(cluster_record)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_gitops_bundle.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifests), "--output-dir", str(gitops_dir)], check=True)
    subprocess.run([sys.executable, "tools/check_fogstack_gitops_bundle.py", "--bundle", str(gitops_dir / "gitops-bundle.json")], check=True)
    subprocess.run([sys.executable, "tools/emit_fogstack_gitops_readiness_record.py", "--bundle", str(gitops_dir / "gitops-bundle.json"), "--output", str(gitops_record)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_local_cluster_runtime_adapter.py", "--deploy-plan", str(deploy_plan), "--cluster-readiness-record", str(cluster_record), "--gitops-bundle", str(gitops_dir / "gitops-bundle.json"), "--gitops-readiness-record", str(gitops_record), "--output", str(adapter)], check=True)
    return adapter, manifests


def test_emit_fogstack_runtime_dry_run_record(tmp_path: Path) -> None:
    adapter, manifests = build_inputs(tmp_path)
    output = tmp_path / "runtime-dry-run.json"
    subprocess.run([sys.executable, "tools/emit_fogstack_runtime_dry_run_record.py", "--runtime-adapter", str(adapter), "--manifest-dir", str(manifests), "--output", str(output)], check=True)
    record = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(record)
    assert record["kind"] == "FogStackRuntimeDryRunRecord"
    assert record["status"] == "passed"
    assert record["bundle_id"] == "fogstack.access"
    assert record["namespace"] == "fogstack-access"
    assert record["dry_run_result"]["mutated_cluster"] is False
    assert record["dry_run_result"]["validation_path"] == "contract-and-digest-only"
    assert record["runtime_policy"]["live_apply_allowed"] is False
    assert len(record["kubernetes_manifests"]) == 3
    assert {artifact["id"] for artifact in record["artifacts"]} == {"runtime-adapter", "deploy-plan", "cluster-readiness-record", "gitops-bundle", "gitops-readiness-record", "kubernetes-configmap", "kubernetes-deployment", "kubernetes-service"}


def test_emit_fogstack_runtime_dry_run_record_rejects_tampered_input(tmp_path: Path) -> None:
    adapter, manifests = build_inputs(tmp_path)
    data = load_json(adapter)
    data["inputs"]["deploy_plan_digest"] = "sha256:" + ("0" * 64)
    adapter.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    output = tmp_path / "runtime-dry-run.json"
    proc = subprocess.run([sys.executable, "tools/emit_fogstack_runtime_dry_run_record.py", "--runtime-adapter", str(adapter), "--manifest-dir", str(manifests), "--output", str(output)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "deploy plan digest mismatch" in proc.stderr
