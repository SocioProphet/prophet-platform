from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
LABEL_PREFIX = "fogstack.socioprophet.io"


def build_inputs(tmp_path: Path) -> tuple[Path, Path]:
    contract = tmp_path / "runtime-contract.json"
    plan = tmp_path / "deploy-plan.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_runtime_contract.py",
        "--bundle-id", "fogstack.access",
        "--version", "0.1.0",
        "--actor-id", "agent:fogstack.access.operator",
        "--human-anchor-role", "operator",
        "--runtime-mode", "local",
        "--isolation", "process",
        "--identity-mode", "local-dev",
        "--max-runtime-seconds", "900",
        "--output", str(contract),
    ], check=True)
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_deploy_plan.py",
        "--manifest", str(MANIFEST),
        "--profile", "local-dev",
        "--target", "kubernetes",
        "--namespace", "fogstack-access",
        "--health-endpoint", "/healthz",
        "--runtime-contract", str(contract),
        "--output", str(plan),
    ], check=True)
    return contract, plan


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_render_fogstack_kubernetes_manifests(tmp_path: Path) -> None:
    contract, plan = build_inputs(tmp_path)
    output_dir = tmp_path / "kubernetes"
    subprocess.run([
        sys.executable,
        "tools/render_fogstack_kubernetes_manifests.py",
        "--deploy-plan", str(plan),
        "--output-dir", str(output_dir),
        "--image", "ghcr.io/socioprophet/fogstack-access:0.1.0",
        "--port", "8080",
    ], check=True)

    config_map = load_yaml(output_dir / "configmap.yaml")
    deployment = load_yaml(output_dir / "deployment.yaml")
    service = load_yaml(output_dir / "service.yaml")
    plan_data = json.loads(plan.read_text(encoding="utf-8"))

    assert config_map["kind"] == "ConfigMap"
    assert config_map["metadata"]["name"] == "fogstack-access-config"
    assert config_map["metadata"]["namespace"] == "fogstack-access"
    assert config_map["data"]["agent_corps_plan_ref"] == str(contract)
    assert config_map["data"]["agent_corps_plan_digest"] == plan_data["agent_corps_plan_digest"]

    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "fogstack-access"
    assert deployment["metadata"]["labels"][f"{LABEL_PREFIX}/bundle-id"] == "fogstack.access"
    assert deployment["metadata"]["labels"][f"{LABEL_PREFIX}/agent-corps"] == "enabled"
    assert deployment["metadata"]["annotations"][f"{LABEL_PREFIX}/agent-corps-plan-ref"] == str(contract)
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "ghcr.io/socioprophet/fogstack-access:0.1.0"
    assert container["readinessProbe"]["httpGet"] == {"path": "/healthz", "port": "http"}
    assert container["livenessProbe"]["httpGet"] == {"path": "/healthz", "port": "http"}

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "fogstack-access"
    assert service["metadata"]["labels"][f"{LABEL_PREFIX}/agent-corps"] == "enabled"
    assert service["spec"]["selector"][f"{LABEL_PREFIX}/bundle-id"] == "fogstack.access"
    assert service["spec"]["ports"] == [{"name": "http", "port": 8080, "targetPort": "http"}]


def test_render_fogstack_kubernetes_manifests_requires_agent_corps_link(tmp_path: Path) -> None:
    _contract, plan = build_inputs(tmp_path)
    output_dir = tmp_path / "kubernetes"
    data = json.loads(plan.read_text(encoding="utf-8"))
    del data["agent_corps_plan_ref"]
    plan.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    proc = subprocess.run([
        sys.executable,
        "tools/render_fogstack_kubernetes_manifests.py",
        "--deploy-plan", str(plan),
        "--output-dir", str(output_dir),
    ], capture_output=True, text=True)

    assert proc.returncode != 0
    assert "Agent Corps" in proc.stderr
