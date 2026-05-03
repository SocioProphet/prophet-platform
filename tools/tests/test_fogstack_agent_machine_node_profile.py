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


def assert_use_surfaces(profile: dict) -> None:
    surfaces = {surface["id"]: surface for surface in profile["use_surfaces"]}
    assert {"turtleterm", "bearbrowser"}.issubset(surfaces)
    turtleterm = surfaces["turtleterm"]
    assert turtleterm["name"] == "TurtleTerm"
    assert turtleterm["surface_type"] == "terminal"
    assert turtleterm["repo_ref"] == "github://SourceOS-Linux/TurtleTerm"
    assert turtleterm["first_class"] is True
    assert turtleterm["agentplane_visible"] is True
    assert turtleterm["policyplane_guarded"] is True
    assert "agent-command-session" in turtleterm["capabilities"]
    assert "node-debug-console" in turtleterm["capabilities"]

    bearbrowser = surfaces["bearbrowser"]
    assert bearbrowser["name"] == "BearBrowser"
    assert bearbrowser["surface_type"] == "browser"
    assert bearbrowser["repo_ref"] == "github://SourceOS-Linux/BearBrowser"
    assert bearbrowser["first_class"] is True
    assert bearbrowser["agentplane_visible"] is True
    assert bearbrowser["policyplane_guarded"] is True
    assert "operator-web-console" in bearbrowser["capabilities"]
    assert "policy-gated-browsing" in bearbrowser["capabilities"]


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
    assert_use_surfaces(profile)
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
    assert_use_surfaces(profile)
