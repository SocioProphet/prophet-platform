from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
SCHEMA = Path("schemas/runtime/fogstack-local-cluster-runtime-adapter-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def build_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    node_profile = tmp_path / "node-profile.json"
    contract = tmp_path / "runtime-contract.json"
    deploy_plan = tmp_path / "deploy-plan.json"
    manifests = tmp_path / "manifests"
    cluster_record = tmp_path / "cluster-readiness.json"
    gitops_dir = tmp_path / "gitops"
    gitops_record = tmp_path / "gitops-readiness.json"
    subprocess.run([sys.executable, "tools/build_fogstack_agent_machine_node_profile.py", "--output", str(node_profile)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_runtime_contract.py", "--bundle-id", "fogstack.access", "--version", "0.1.0", "--actor-id", "agent:fogstack.access.operator", "--human-anchor-role", "operator", "--output", str(contract)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_deploy_plan.py", "--manifest", str(MANIFEST), "--profile", "local-dev", "--target", "kubernetes", "--namespace", "fogstack-access", "--health-endpoint", "/healthz", "--runtime-contract", str(contract), "--output", str(deploy_plan)], check=True)
    subprocess.run([sys.executable, "tools/render_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--output-dir", str(manifests)], check=True)
    subprocess.run([sys.executable, "tools/check_fogstack_kubernetes_manifests.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifests), "--record-output", str(cluster_record)], check=True)
    subprocess.run([sys.executable, "tools/build_fogstack_gitops_bundle.py", "--deploy-plan", str(deploy_plan), "--manifest-dir", str(manifests), "--output-dir", str(gitops_dir)], check=True)
    subprocess.run([sys.executable, "tools/check_fogstack_gitops_bundle.py", "--bundle", str(gitops_dir / "gitops-bundle.json")], check=True)
    subprocess.run([sys.executable, "tools/emit_fogstack_gitops_readiness_record.py", "--bundle", str(gitops_dir / "gitops-bundle.json"), "--output", str(gitops_record)], check=True)
    return node_profile, deploy_plan, cluster_record, gitops_dir / "gitops-bundle.json", gitops_record


def test_build_fogstack_local_cluster_runtime_adapter(tmp_path: Path) -> None:
    node_profile, deploy_plan, cluster_record, gitops_bundle, gitops_record = build_inputs(tmp_path)
    output = tmp_path / "local-cluster-runtime-adapter.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_local_cluster_runtime_adapter.py",
        "--node-profile", str(node_profile),
        "--deploy-plan", str(deploy_plan),
        "--cluster-readiness-record", str(cluster_record),
        "--gitops-bundle", str(gitops_bundle),
        "--gitops-readiness-record", str(gitops_record),
        "--output", str(output),
    ], check=True)
    adapter = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(adapter)
    assert adapter["kind"] == "FogStackLocalClusterRuntimeAdapter"
    assert adapter["bundle_id"] == "fogstack.access"
    assert adapter["version"] == "0.1.0"
    assert adapter["namespace"] == "fogstack-access"
    assert adapter["adapter"]["mode"] == "dry-run"
    assert adapter["adapter"]["cluster_provider"] == "kind"
    assert adapter["adapter"]["supported_tools"] == ["kubectl", "kind"]
    assert adapter["runtime_policy"] == {
        "live_apply_allowed": False,
        "requires_human_approval": True,
        "network_default": "deny",
        "secrets_default": "deny",
    }
    for key in ["node_profile_digest", "deploy_plan_digest", "cluster_readiness_record_digest", "gitops_bundle_digest", "gitops_readiness_record_digest"]:
        assert adapter["inputs"][key].startswith("sha256:")
    node = load_json(adapter["inputs"]["node_profile_ref"])
    surfaces = {surface["id"]: surface for surface in node["use_surfaces"]}
    assert surfaces["turtleterm"]["repo_ref"] == "github://SourceOS-Linux/TurtleTerm"
    assert surfaces["bearbrowser"]["repo_ref"] == "github://SourceOS-Linux/BearBrowser"
    artifact_ids = {artifact["id"] for artifact in adapter["artifacts"]}
    assert artifact_ids == {"node-profile", "deploy-plan", "cluster-readiness-record", "gitops-bundle", "gitops-readiness-record"}
