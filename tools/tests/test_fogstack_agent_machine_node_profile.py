from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/runtime/fogstack-agent-machine-node-profile-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_build_fogstack_agent_machine_node_profile(tmp_path: Path) -> None:
    output = tmp_path / "agent-machine-node-profile.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_agent_machine_node_profile.py",
        "--output", str(output),
    ], check=True)

    profile = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(profile)
    assert profile["kind"] == "FogStackAgentMachineNodeProfile"
    assert profile["profile_id"] == "sourceos.agent-machine.edge.v0.1"
    assert profile["node_role"] == "edge-agent-node"
    assert profile["os"] == {
        "family": "SourceOS",
        "distribution": "SourceOS-Linux",
        "immutability": "nixos",
        "configuration_model": "nix-flake",
    }
    assert profile["image"]["builder"] == "nix"
    assert profile["image"]["digest_required"] is True
    assert profile["image"]["sbom_required"] is True
    assert profile["image"]["provenance_required"] is True
    assert profile["declarative_updates"] == {
        "strategy": "nix-flake-switch",
        "rollback_required": True,
        "preflight_required": True,
        "agentplane_gate_required": True,
    }
    assert profile["storage"]["topolvm_required"] is True
    assert profile["storage"]["persistent_storage"] == "topolvm"
    assert profile["agent_machine"]["enabled"] is True
    assert profile["agent_machine"]["node_contract_required"] is True
    assert profile["governance"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert profile["governance"]["policyplane_ref"] == "github://SocioProphet/policy-fabric"
    assert profile["governance"]["human_approval_required"] is True
    assert profile["governance"]["live_mutation_default"] == "deny"
    assert profile["runtime_policy"] == {
        "network_default": "deny",
        "secrets_default": "deny",
        "host_mutation_default": "deny",
        "cluster_join_default": "approval-required",
    }


def test_build_agentos_node_profile_without_topolvm(tmp_path: Path) -> None:
    output = tmp_path / "agentos-node-profile.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_agent_machine_node_profile.py",
        "--output", str(output),
        "--os-family", "AgentOS",
        "--distribution", "AgentOS-Linux",
        "--immutability", "ostree",
        "--configuration-model", "rpm-ostree",
        "--image-builder", "rpm-ostree",
        "--update-strategy", "ostree-rebase",
        "--no-topolvm",
    ], check=True)

    profile = load_json(output)
    Draft202012Validator(load_json(SCHEMA)).validate(profile)
    assert profile["os"]["family"] == "AgentOS"
    assert profile["os"]["immutability"] == "ostree"
    assert profile["declarative_updates"]["strategy"] == "ostree-rebase"
    assert profile["storage"]["topolvm_required"] is False
    assert profile["storage"]["persistent_storage"] == "external-csi"
