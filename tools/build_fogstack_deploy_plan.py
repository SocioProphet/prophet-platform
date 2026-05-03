#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected YAML object in {path}")
    return data


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def selected_profile(bundle: dict[str, Any], profile_id: str) -> dict[str, Any]:
    profiles = bundle.get("profiles", {}).get("supported", [])
    if not isinstance(profiles, list):
        raise SystemExit("ERR: bundle profiles.supported must be a list")
    for profile in profiles:
        if isinstance(profile, dict) and profile.get("id") == profile_id:
            return profile
    raise SystemExit(f"ERR: profile not found in bundle: {profile_id}")


def build_plan(
    manifest_path: Path,
    profile_id: str,
    target: str,
    namespace: str,
    health_endpoint: str,
    runtime_contract_path: Path,
) -> dict[str, Any]:
    manifest_path = manifest_path if manifest_path.is_absolute() else ROOT / manifest_path
    runtime_contract_path = runtime_contract_path if runtime_contract_path.is_absolute() else ROOT / runtime_contract_path
    manifest = load_json(manifest_path)
    runtime_contract = load_json(runtime_contract_path)

    bundle_ref = manifest.get("bundle")
    if not isinstance(bundle_ref, str) or not bundle_ref:
        raise SystemExit("ERR: manifest missing bundle ref")
    bundle_path = ROOT / bundle_ref
    bundle = load_yaml(bundle_path)

    profile = selected_profile(bundle, profile_id)
    metadata = bundle.get("metadata", {})
    runtime = bundle.get("runtime", {})
    deployment = bundle.get("deployment", {})
    contracts = bundle.get("contracts", {})
    security = bundle.get("security", {})

    bundle_id = manifest.get("bundle_id")
    version = manifest.get("version")
    if bundle_id != metadata.get("bundle_id"):
        raise SystemExit("ERR: manifest bundle_id does not match bundle metadata")
    if version != metadata.get("version"):
        raise SystemExit("ERR: manifest version does not match bundle metadata")
    if runtime_contract.get("kind") != "FogStackAgentCorpsPlan":
        raise SystemExit("ERR: runtime contract must be a FogStackAgentCorpsPlan")
    if runtime_contract.get("bundle_id") != bundle_id:
        raise SystemExit("ERR: runtime contract bundle_id does not match manifest")
    if runtime_contract.get("version") != version:
        raise SystemExit("ERR: runtime contract version does not match manifest")

    manifest_digest = sha256_file(manifest_path)
    runtime_contract_digest = sha256_file(runtime_contract_path)
    bundle_digest = manifest.get("bundle_digest")
    if not isinstance(bundle_digest, str) or not bundle_digest.startswith("sha256:"):
        raise SystemExit("ERR: manifest bundle_digest missing or malformed")

    runtime_contract_ref = rel(runtime_contract_path)
    return {
        "kind": "FogStackDeployPlan",
        "schema_version": "v0.1",
        "bundle_id": bundle_id,
        "version": version,
        "profile": profile_id,
        "target": target,
        "namespace": namespace,
        "manifest_ref": rel(manifest_path),
        "manifest_digest": manifest_digest,
        "bundle_ref": bundle_ref,
        "bundle_digest": bundle_digest,
        "agent_corps_plan_ref": runtime_contract_ref,
        "agent_corps_plan_digest": runtime_contract_digest,
        "runtime": {
            "substrate": runtime.get("substrate"),
            "service_classes": runtime.get("service_classes", []),
            "components": runtime.get("components", []),
        },
        "deployment": {
            "minimum_nodes_for_first_value": deployment.get("minimum_nodes_for_first_value"),
            "max_required_services": deployment.get("max_required_services"),
            "install_time_target_minutes": deployment.get("install_time_target_minutes"),
            "kubernetes_required": bool(profile.get("kubernetes_required")),
            "root_required": bool(profile.get("root_required")),
            "health_endpoint": health_endpoint,
        },
        "artifacts": [
            {
                "id": "bundle",
                "ref": bundle_ref,
                "digest": bundle_digest,
            },
            {
                "id": "manifest",
                "ref": rel(manifest_path),
                "digest": manifest_digest,
            },
            {
                "id": "agent-corps-plan",
                "ref": runtime_contract_ref,
                "digest": runtime_contract_digest,
            },
        ],
        "policy": {
            "required_contracts": contracts.get("required", []),
            "security_claims": {
                "operator_identity": bool(security.get("identities", {}).get("operator_identity")),
                "node_identity": bool(security.get("identities", {}).get("node_identity")),
                "workload_identity": bool(security.get("identities", {}).get("workload_identity")),
                "peer_identity": bool(security.get("identities", {}).get("peer_identity")),
                "signed_artifacts": bool(security.get("supply_chain", {}).get("signed_artifacts")),
                "sbom_required": bool(security.get("supply_chain", {}).get("sbom_required")),
                "provenance_required": bool(security.get("supply_chain", {}).get("provenance_required")),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FogStack deploy plan from a bundle manifest")
    parser.add_argument("--manifest", default="releases/manifests/fogstack.access-v0.1.manifest.json", type=Path)
    parser.add_argument("--profile", default="local-dev")
    parser.add_argument("--target", choices=["local", "kubernetes", "openshift"], default="local")
    parser.add_argument("--namespace", default="fogstack-access")
    parser.add_argument("--health-endpoint", default="/healthz")
    parser.add_argument("--runtime-contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plan = build_plan(
        args.manifest,
        args.profile,
        args.target,
        args.namespace,
        args.health_endpoint,
        args.runtime_contract,
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
