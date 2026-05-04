#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SURFACES = {"turtleterm", "bearbrowser"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def compact_surface(surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": surface["id"],
        "repo_ref": surface["repo_ref"],
        "first_class": surface["first_class"],
        "agentplane_visible": surface["agentplane_visible"],
        "policyplane_guarded": surface["policyplane_guarded"],
    }


def emit_record(
    node_profile_path: Path,
    output_path: Path,
    node_id: str,
    cluster_provider: str,
    cluster_role: str,
) -> dict[str, Any]:
    node_profile_path = resolve(node_profile_path)
    output_path = resolve(output_path)
    node_profile = load_json(node_profile_path)
    if node_profile.get("kind") != "FogStackAgentMachineNodeProfile":
        raise SystemExit("ERR: expected FogStackAgentMachineNodeProfile")

    surfaces = {surface.get("id"): surface for surface in node_profile.get("use_surfaces", []) if isinstance(surface, dict)}
    missing = REQUIRED_SURFACES - set(surfaces)
    if missing:
        raise SystemExit(f"ERR: missing required use surfaces: {', '.join(sorted(missing))}")

    storage = node_profile["storage"]
    agent_machine = node_profile["agent_machine"]
    governance = node_profile["governance"]
    runtime_policy = node_profile["runtime_policy"]
    readiness = {
        "node_profile_ready": True,
        "agent_machine_ready": agent_machine.get("enabled") is True and agent_machine.get("node_contract_required") is True,
        "storage_ready": storage.get("topolvm_required") is False or storage.get("persistent_storage") == "topolvm",
        "surfaces_ready": all(
            surfaces[surface_id].get("first_class") is True
            and surfaces[surface_id].get("agentplane_visible") is True
            and surfaces[surface_id].get("policyplane_guarded") is True
            for surface_id in REQUIRED_SURFACES
        ),
        "governance_ready": bool(governance.get("agentplane_ref")) and bool(governance.get("policyplane_ref")) and governance.get("human_approval_required") is True,
        "cluster_join_ready": runtime_policy.get("cluster_join_default") == "approval-required",
    }
    status = "passed" if all(readiness.values()) and runtime_policy.get("host_mutation_default") == "deny" else "failed"

    record = {
        "kind": "FogStackAgentMachineNodeInventoryRecord",
        "schema_version": "v0.1",
        "status": status,
        "node_profile_ref": rel(node_profile_path),
        "node_profile_digest": sha256_file(node_profile_path),
        "inventory": {
            "node_id": node_id,
            "node_role": node_profile["node_role"],
            "os_family": node_profile["os"]["family"],
            "distribution": node_profile["os"]["distribution"],
            "immutability": node_profile["os"]["immutability"],
            "configuration_model": node_profile["os"]["configuration_model"],
        },
        "storage": {
            "topolvm_required": storage["topolvm_required"],
            "ephemeral_storage": storage["ephemeral_storage"],
            "persistent_storage": storage["persistent_storage"],
            "volume_policy": storage["volume_policy"],
            "storage_ready": readiness["storage_ready"],
        },
        "agent_machine": {
            "enabled": agent_machine["enabled"],
            "identity_ref": agent_machine["identity_ref"],
            "workload_runtime": agent_machine["workload_runtime"],
            "node_contract_required": agent_machine["node_contract_required"],
            "use_surfaces": [compact_surface(surfaces[surface_id]) for surface_id in sorted(REQUIRED_SURFACES)],
        },
        "cluster": {
            "cluster_provider": cluster_provider,
            "cluster_role": cluster_role,
            "join_policy": "approval-required",
            "mutation_default": "deny",
        },
        "governance": governance,
        "readiness": readiness,
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a FogStack Agent Machine node inventory record")
    parser.add_argument("--node-profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--node-id", default="agent-machine://sourceos/edge/default")
    parser.add_argument("--cluster-provider", choices=["kind", "generic-kubernetes", "future-agentos-cluster"], default="kind")
    parser.add_argument("--cluster-role", choices=["worker", "control-plane", "single-node"], default="worker")
    args = parser.parse_args()
    record = emit_record(args.node_profile, args.output, args.node_id, args.cluster_provider, args.cluster_role)
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
