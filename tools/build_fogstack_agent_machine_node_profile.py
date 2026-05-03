#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_profile(
    profile_id: str,
    node_role: str,
    os_family: str,
    distribution: str,
    immutability: str,
    configuration_model: str,
    image_builder: str,
    image_ref: str,
    update_strategy: str,
    topolvm_required: bool,
    agent_identity_ref: str,
    workload_runtime: str,
    agentplane_ref: str,
    policyplane_ref: str,
) -> dict[str, Any]:
    persistent_storage = "topolvm" if topolvm_required else "external-csi"
    ephemeral_storage = "topolvm" if topolvm_required else "local"
    return {
        "kind": "FogStackAgentMachineNodeProfile",
        "schema_version": "v0.1",
        "profile_id": profile_id,
        "node_role": node_role,
        "os": {
            "family": os_family,
            "distribution": distribution,
            "immutability": immutability,
            "configuration_model": configuration_model,
        },
        "image": {
            "builder": image_builder,
            "image_ref": image_ref,
            "digest_required": True,
            "sbom_required": True,
            "provenance_required": True,
        },
        "declarative_updates": {
            "strategy": update_strategy,
            "rollback_required": True,
            "preflight_required": True,
            "agentplane_gate_required": True,
        },
        "storage": {
            "ephemeral_storage": ephemeral_storage,
            "persistent_storage": persistent_storage,
            "topolvm_required": topolvm_required,
            "volume_policy": "explicit-claim-only",
        },
        "agent_machine": {
            "enabled": True,
            "identity_ref": agent_identity_ref,
            "workload_runtime": workload_runtime,
            "node_contract_required": True,
        },
        "governance": {
            "agentplane_ref": agentplane_ref,
            "policyplane_ref": policyplane_ref,
            "human_approval_required": True,
            "live_mutation_default": "deny",
        },
        "runtime_policy": {
            "network_default": "deny",
            "secrets_default": "deny",
            "host_mutation_default": "deny",
            "cluster_join_default": "approval-required",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FogStack Agent Machine node profile")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile-id", default="sourceos.agent-machine.edge.v0.1")
    parser.add_argument("--node-role", choices=["edge-agent-node", "cluster-agent-node", "control-plane-agent-node"], default="edge-agent-node")
    parser.add_argument("--os-family", choices=["SourceOS", "AgentOS", "SociOS-Linux"], default="SourceOS")
    parser.add_argument("--distribution", default="SourceOS-Linux")
    parser.add_argument("--immutability", choices=["ostree", "nixos", "image-based", "unknown"], default="nixos")
    parser.add_argument("--configuration-model", choices=["nix-flake", "ignition-butane", "rpm-ostree", "container-image", "hybrid"], default="nix-flake")
    parser.add_argument("--image-builder", choices=["nix", "rpm-ostree", "bootc", "containerfile", "unknown"], default="nix")
    parser.add_argument("--image-ref", default="sourceos://images/agent-machine-edge@v0.1")
    parser.add_argument("--update-strategy", choices=["nix-flake-switch", "ostree-rebase", "image-promotion", "hybrid"], default="nix-flake-switch")
    parser.add_argument("--topolvm-required", action="store_true", default=True)
    parser.add_argument("--no-topolvm", dest="topolvm_required", action="store_false")
    parser.add_argument("--agent-identity-ref", default="agent-machine://sourceos/edge/default")
    parser.add_argument("--workload-runtime", choices=["rootless-podman", "kubernetes", "systemd-user", "hybrid"], default="hybrid")
    parser.add_argument("--agentplane-ref", default="github://SocioProphet/agentplane")
    parser.add_argument("--policyplane-ref", default="github://SocioProphet/policy-fabric")
    args = parser.parse_args()

    profile = build_profile(
        profile_id=args.profile_id,
        node_role=args.node_role,
        os_family=args.os_family,
        distribution=args.distribution,
        immutability=args.immutability,
        configuration_model=args.configuration_model,
        image_builder=args.image_builder,
        image_ref=args.image_ref,
        update_strategy=args.update_strategy,
        topolvm_required=args.topolvm_required,
        agent_identity_ref=args.agent_identity_ref,
        workload_runtime=args.workload_runtime,
        agentplane_ref=args.agentplane_ref,
        policyplane_ref=args.policyplane_ref,
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    write_json(output, profile)
    print(json.dumps(profile, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
