from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/runtime/fogstack-agent-machine-node-inventory-record-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def emit_inventory(node_profile: Path, output: Path, *extra: str) -> dict:
    subprocess.run([
        sys.executable,
        "tools/emit_fogstack_agent_machine_node_inventory_record.py",
        "--node-profile", str(node_profile),
        "--output", str(output),
        *extra,
    ], check=True)
    return load_json(output)


def assert_required_surfaces(record: dict) -> None:
    surfaces = {surface["id"]: surface for surface in record["agent_machine"]["use_surfaces"]}
    assert surfaces["turtleterm"]["repo_ref"] == "github://SourceOS-Linux/TurtleTerm"
    assert surfaces["turtleterm"]["first_class"] is True
    assert surfaces["turtleterm"]["agentplane_visible"] is True
    assert surfaces["turtleterm"]["policyplane_guarded"] is True
    assert surfaces["bearbrowser"]["repo_ref"] == "github://SourceOS-Linux/BearBrowser"
    assert surfaces["bearbrowser"]["first_class"] is True
    assert surfaces["bearbrowser"]["agentplane_visible"] is True
    assert surfaces["bearbrowser"]["policyplane_guarded"] is True


def test_emit_agent_machine_node_inventory_sourceos_topolvm(tmp_path: Path) -> None:
    node_profile = tmp_path / "sourceos-node-profile.json"
    output = tmp_path / "node-inventory.json"
    subprocess.run([sys.executable, "tools/build_fogstack_agent_machine_node_profile.py", "--output", str(node_profile)], check=True)

    record = emit_inventory(node_profile, output)
    Draft202012Validator(load_json(SCHEMA)).validate(record)
    assert record["kind"] == "FogStackAgentMachineNodeInventoryRecord"
    assert record["status"] == "passed"
    assert record["inventory"]["node_role"] == "edge-agent-node"
    assert record["inventory"]["os_family"] == "SourceOS"
    assert record["inventory"]["immutability"] == "nixos"
    assert record["inventory"]["configuration_model"] == "nix-flake"
    assert record["storage"]["topolvm_required"] is True
    assert record["storage"]["persistent_storage"] == "topolvm"
    assert record["storage"]["storage_ready"] is True
    assert record["agent_machine"]["enabled"] is True
    assert record["agent_machine"]["node_contract_required"] is True
    assert_required_surfaces(record)
    assert record["cluster"] == {
        "cluster_provider": "kind",
        "cluster_role": "worker",
        "join_policy": "approval-required",
        "mutation_default": "deny",
    }
    assert record["governance"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert record["governance"]["policyplane_ref"] == "github://SocioProphet/policy-fabric"
    assert all(record["readiness"].values())


def test_emit_agent_machine_node_inventory_agentos_external_csi(tmp_path: Path) -> None:
    node_profile = tmp_path / "agentos-node-profile.json"
    output = tmp_path / "node-inventory.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_agent_machine_node_profile.py",
        "--output", str(node_profile),
        "--os-family", "AgentOS",
        "--distribution", "AgentOS-Linux",
        "--immutability", "ostree",
        "--configuration-model", "rpm-ostree",
        "--image-builder", "rpm-ostree",
        "--update-strategy", "ostree-rebase",
        "--no-topolvm",
    ], check=True)

    record = emit_inventory(node_profile, output, "--cluster-provider", "generic-kubernetes", "--cluster-role", "single-node")
    Draft202012Validator(load_json(SCHEMA)).validate(record)
    assert record["status"] == "passed"
    assert record["inventory"]["os_family"] == "AgentOS"
    assert record["inventory"]["immutability"] == "ostree"
    assert record["storage"]["topolvm_required"] is False
    assert record["storage"]["persistent_storage"] == "external-csi"
    assert record["storage"]["storage_ready"] is True
    assert record["cluster"]["cluster_provider"] == "generic-kubernetes"
    assert record["cluster"]["cluster_role"] == "single-node"
    assert_required_surfaces(record)
    assert all(record["readiness"].values())
