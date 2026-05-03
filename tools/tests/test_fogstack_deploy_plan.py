from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/deploy/fogstack-deploy-plan-v0.1.schema.json")
MANIFEST = Path("releases/manifests/fogstack.access-v0.1.manifest.json")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def build_runtime_contract(output: Path, *, bundle_id: str = "fogstack.access", version: str = "0.1.0") -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_runtime_contract.py",
            "--bundle-id",
            bundle_id,
            "--version",
            version,
            "--actor-id",
            "agent:fogstack.access.operator",
            "--human-anchor-role",
            "operator",
            "--runtime-mode",
            "local",
            "--isolation",
            "process",
            "--identity-mode",
            "local-dev",
            "--max-runtime-seconds",
            "900",
            "--output",
            str(output),
        ],
        check=True,
    )


def build_deploy_plan(output: Path, runtime_contract: Path, *, profile: str = "local-dev", target: str = "local") -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_deploy_plan.py",
            "--manifest",
            str(MANIFEST),
            "--profile",
            profile,
            "--target",
            target,
            "--namespace",
            "fogstack-access",
            "--health-endpoint",
            "/healthz",
            "--runtime-contract",
            str(runtime_contract),
            "--output",
            str(output),
        ],
        check=True,
    )


def test_build_fogstack_access_deploy_plan(tmp_path: Path) -> None:
    runtime_contract = tmp_path / "fogstack.access.runtime-contract.json"
    output = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(runtime_contract)
    build_deploy_plan(output, runtime_contract)

    plan = load_json(output)
    schema = load_json(SCHEMA)
    Draft202012Validator(schema).validate(plan)

    assert plan["kind"] == "FogStackDeployPlan"
    assert plan["schema_version"] == "v0.1"
    assert plan["bundle_id"] == "fogstack.access"
    assert plan["version"] == "0.1.0"
    assert plan["profile"] == "local-dev"
    assert plan["target"] == "local"
    assert plan["namespace"] == "fogstack-access"
    assert plan["manifest_ref"] == str(MANIFEST)
    assert plan["bundle_ref"] == "bundles/fogstack.access-v0.1.yaml"
    assert plan["agent_corps_plan_ref"] == str(runtime_contract)
    assert DIGEST_RE.match(plan["manifest_digest"])
    assert DIGEST_RE.match(plan["bundle_digest"])
    assert DIGEST_RE.match(plan["agent_corps_plan_digest"])

    assert plan["runtime"]["substrate"] == "prophet-platform"
    assert plan["runtime"]["service_classes"] == ["edge-service", "cluster-service"]
    component_ids = {component["id"] for component in plan["runtime"]["components"]}
    assert component_ids == {"cloudshell-fog", "apps/gateway", "apps/api"}

    assert plan["deployment"]["minimum_nodes_for_first_value"] == 1
    assert plan["deployment"]["max_required_services"] == 3
    assert plan["deployment"]["install_time_target_minutes"] == 30
    assert plan["deployment"]["kubernetes_required"] is False
    assert plan["deployment"]["root_required"] is False
    assert plan["deployment"]["health_endpoint"] == "/healthz"

    artifacts = {artifact["id"]: artifact for artifact in plan["artifacts"]}
    assert set(artifacts) == {"bundle", "manifest", "agent-corps-plan"}
    assert artifacts["bundle"]["ref"] == plan["bundle_ref"]
    assert artifacts["bundle"]["digest"] == plan["bundle_digest"]
    assert artifacts["manifest"]["ref"] == plan["manifest_ref"]
    assert artifacts["manifest"]["digest"] == plan["manifest_digest"]
    assert artifacts["agent-corps-plan"]["ref"] == plan["agent_corps_plan_ref"]
    assert artifacts["agent-corps-plan"]["digest"] == plan["agent_corps_plan_digest"]

    assert plan["policy"]["required_contracts"] == [
        "EventEnvelope",
        "EvidenceReceipt",
        "MembraneDecision",
    ]
    assert plan["policy"]["security_claims"] == {
        "operator_identity": True,
        "node_identity": True,
        "workload_identity": True,
        "peer_identity": True,
        "signed_artifacts": True,
        "sbom_required": True,
        "provenance_required": True,
    }


def test_build_fogstack_access_cluster_profile(tmp_path: Path) -> None:
    runtime_contract = tmp_path / "fogstack.access.runtime-contract.json"
    output = tmp_path / "fogstack.access.cluster.deploy-plan.json"
    build_runtime_contract(runtime_contract)
    build_deploy_plan(output, runtime_contract, profile="cluster-standard", target="kubernetes")

    plan = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(plan)
    assert plan["profile"] == "cluster-standard"
    assert plan["target"] == "kubernetes"
    assert plan["agent_corps_plan_ref"] == str(runtime_contract)
    assert plan["deployment"]["kubernetes_required"] is True
    assert plan["deployment"]["root_required"] is False


def test_build_fogstack_deploy_plan_rejects_mismatched_runtime_contract(tmp_path: Path) -> None:
    runtime_contract = tmp_path / "fogstack.knowledge.runtime-contract.json"
    output = tmp_path / "fogstack.access.deploy-plan.json"
    build_runtime_contract(runtime_contract, bundle_id="fogstack.knowledge")

    proc = subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_deploy_plan.py",
            "--manifest",
            str(MANIFEST),
            "--profile",
            "local-dev",
            "--target",
            "local",
            "--namespace",
            "fogstack-access",
            "--runtime-contract",
            str(runtime_contract),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "runtime contract bundle_id does not match manifest" in proc.stderr
