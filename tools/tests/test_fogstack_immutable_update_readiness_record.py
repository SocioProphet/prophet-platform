from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA = Path("schemas/runtime/fogstack-immutable-update-readiness-record-v0.1.schema.json")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def emit_record(node_profile: Path, output: Path) -> dict:
    subprocess.run([
        sys.executable,
        "tools/emit_fogstack_immutable_update_readiness_record.py",
        "--node-profile", str(node_profile),
        "--output", str(output),
    ], check=True)
    return load_json(output)


def test_emit_immutable_update_readiness_record_sourceos_nix(tmp_path: Path) -> None:
    node_profile = tmp_path / "sourceos-node-profile.json"
    output = tmp_path / "immutable-update-readiness.json"
    subprocess.run([sys.executable, "tools/build_fogstack_agent_machine_node_profile.py", "--output", str(node_profile)], check=True)

    record = emit_record(node_profile, output)
    Draft202012Validator(load_json(SCHEMA)).validate(record)
    assert record["kind"] == "FogStackImmutableUpdateReadinessRecord"
    assert record["status"] == "passed"
    assert record["os"]["family"] == "SourceOS"
    assert record["os"]["immutability"] == "nixos"
    assert record["os"]["configuration_model"] == "nix-flake"
    assert record["image"]["builder"] == "nix"
    assert record["image"]["digest_required"] is True
    assert record["image"]["sbom_required"] is True
    assert record["image"]["provenance_required"] is True
    assert record["declarative_updates"]["strategy"] == "nix-flake-switch"
    assert record["declarative_updates"]["rollback_required"] is True
    assert record["declarative_updates"]["preflight_required"] is True
    assert record["declarative_updates"]["agentplane_gate_required"] is True
    assert record["governance"]["agentplane_ref"] == "github://SocioProphet/agentplane"
    assert record["governance"]["policyplane_ref"] == "github://SocioProphet/policy-fabric"
    assert record["policy"] == {
        "host_mutation_default": "deny",
        "cluster_join_default": "approval-required",
        "live_update_allowed": False,
        "requires_agentplane_gate": True,
        "requires_policyplane_decision": True,
    }
    assert all(record["readiness"].values())


def test_emit_immutable_update_readiness_record_agentos_ostree(tmp_path: Path) -> None:
    node_profile = tmp_path / "agentos-node-profile.json"
    output = tmp_path / "immutable-update-readiness.json"
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

    record = emit_record(node_profile, output)
    Draft202012Validator(load_json(SCHEMA)).validate(record)
    assert record["status"] == "passed"
    assert record["os"]["family"] == "AgentOS"
    assert record["os"]["immutability"] == "ostree"
    assert record["os"]["configuration_model"] == "rpm-ostree"
    assert record["image"]["builder"] == "rpm-ostree"
    assert record["declarative_updates"]["strategy"] == "ostree-rebase"
    assert all(record["readiness"].values())
