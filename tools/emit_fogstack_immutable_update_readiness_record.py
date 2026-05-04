#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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


def emit_record(node_profile_path: Path, output_path: Path) -> dict[str, Any]:
    node_profile_path = resolve(node_profile_path)
    output_path = resolve(output_path)
    node_profile = load_json(node_profile_path)
    if node_profile.get("kind") != "FogStackAgentMachineNodeProfile":
        raise SystemExit("ERR: expected FogStackAgentMachineNodeProfile")

    image = node_profile["image"]
    updates = node_profile["declarative_updates"]
    governance = node_profile["governance"]
    runtime_policy = node_profile["runtime_policy"]
    readiness = {
        "digest_ready": image.get("digest_required") is True,
        "sbom_ready": image.get("sbom_required") is True,
        "provenance_ready": image.get("provenance_required") is True,
        "rollback_ready": updates.get("rollback_required") is True,
        "preflight_ready": updates.get("preflight_required") is True,
        "agentplane_gate_ready": updates.get("agentplane_gate_required") is True and bool(governance.get("agentplane_ref")),
        "policyplane_gate_ready": bool(governance.get("policyplane_ref")),
    }
    status = "passed" if all(readiness.values()) and governance.get("live_mutation_default") == "deny" and runtime_policy.get("host_mutation_default") == "deny" else "failed"

    record = {
        "kind": "FogStackImmutableUpdateReadinessRecord",
        "schema_version": "v0.1",
        "status": status,
        "node_profile_ref": rel(node_profile_path),
        "node_profile_digest": sha256_file(node_profile_path),
        "os": node_profile["os"],
        "image": image,
        "declarative_updates": updates,
        "governance": governance,
        "policy": {
            "host_mutation_default": runtime_policy["host_mutation_default"],
            "cluster_join_default": runtime_policy["cluster_join_default"],
            "live_update_allowed": False,
            "requires_agentplane_gate": True,
            "requires_policyplane_decision": True,
        },
        "readiness": readiness,
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a FogStack immutable/declarative update readiness record")
    parser.add_argument("--node-profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    record = emit_record(args.node_profile, args.output)
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
