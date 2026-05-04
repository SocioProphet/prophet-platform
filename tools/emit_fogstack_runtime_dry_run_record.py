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


def artifact(artifact_id: str, path: Path) -> dict[str, str]:
    path = resolve(path)
    return {"id": artifact_id, "ref": rel(path), "digest": sha256_file(path)}


def require_digest(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"ERR: {label} digest mismatch")


def require_node_surfaces(node_profile: dict[str, Any]) -> None:
    surfaces = {surface.get("id"): surface for surface in node_profile.get("use_surfaces", []) if isinstance(surface, dict)}
    for surface_id in ["turtleterm", "bearbrowser"]:
        surface = surfaces.get(surface_id)
        if not surface:
            raise SystemExit(f"ERR: node profile missing required surface: {surface_id}")
        if surface.get("first_class") is not True:
            raise SystemExit(f"ERR: node surface is not first-class: {surface_id}")
        if surface.get("agentplane_visible") is not True:
            raise SystemExit(f"ERR: node surface is not AgentPlane-visible: {surface_id}")
        if surface.get("policyplane_guarded") is not True:
            raise SystemExit(f"ERR: node surface is not PolicyPlane-guarded: {surface_id}")


def agentplane_run_payload(run_id: str, run_ref: str, agentplane_ref: str, requested_by: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "run_ref": run_ref,
        "agentplane_ref": agentplane_ref,
        "requested_by": requested_by,
        "execution_mode": "dry-run",
        "approval_state": "live-apply-requires-human-approval",
    }


def emit_record(
    adapter_path: Path,
    manifest_dir: Path,
    output_path: Path,
    agentplane_run_id: str,
    agentplane_run_ref: str,
    agentplane_ref: str,
    requested_by: str,
) -> dict[str, Any]:
    adapter_path = resolve(adapter_path)
    manifest_dir = resolve(manifest_dir)
    output_path = resolve(output_path)
    adapter = load_json(adapter_path)
    if adapter.get("kind") != "FogStackLocalClusterRuntimeAdapter":
        raise SystemExit("ERR: expected FogStackLocalClusterRuntimeAdapter")
    if adapter["adapter"]["mode"] != "dry-run":
        raise SystemExit("ERR: runtime adapter must be in dry-run mode")
    if adapter["runtime_policy"]["live_apply_allowed"] is not False:
        raise SystemExit("ERR: live apply must be disabled for dry-run record")

    inputs = adapter["inputs"]
    node_profile_path = resolve(Path(inputs["node_profile_ref"]))
    deploy_plan_path = resolve(Path(inputs["deploy_plan_ref"]))
    cluster_record_path = resolve(Path(inputs["cluster_readiness_record_ref"]))
    gitops_bundle_path = resolve(Path(inputs["gitops_bundle_ref"]))
    gitops_readiness_path = resolve(Path(inputs["gitops_readiness_record_ref"]))
    require_digest(node_profile_path, inputs["node_profile_digest"], "node profile")
    require_digest(deploy_plan_path, inputs["deploy_plan_digest"], "deploy plan")
    require_digest(cluster_record_path, inputs["cluster_readiness_record_digest"], "cluster readiness record")
    require_digest(gitops_bundle_path, inputs["gitops_bundle_digest"], "GitOps bundle")
    require_digest(gitops_readiness_path, inputs["gitops_readiness_record_digest"], "GitOps readiness record")

    node_profile = load_json(node_profile_path)
    deploy_plan = load_json(deploy_plan_path)
    cluster_record = load_json(cluster_record_path)
    gitops_bundle = load_json(gitops_bundle_path)
    gitops_readiness = load_json(gitops_readiness_path)
    if node_profile.get("kind") != "FogStackAgentMachineNodeProfile":
        raise SystemExit("ERR: expected FogStackAgentMachineNodeProfile")
    require_node_surfaces(node_profile)
    if deploy_plan.get("bundle_id") != adapter["bundle_id"] or deploy_plan.get("version") != adapter["version"]:
        raise SystemExit("ERR: deploy plan does not match adapter bundle/version")
    if cluster_record.get("status") != "passed":
        raise SystemExit("ERR: cluster readiness record must have passed status")
    if gitops_bundle.get("bundle_id") != adapter["bundle_id"] or gitops_bundle.get("version") != adapter["version"]:
        raise SystemExit("ERR: GitOps bundle does not match adapter bundle/version")
    if gitops_readiness.get("status") != "passed":
        raise SystemExit("ERR: GitOps readiness record must have passed status")
    if agentplane_ref != node_profile["governance"].get("agentplane_ref"):
        raise SystemExit("ERR: AgentPlane run ref does not match node profile governance")

    manifest_paths = [
        manifest_dir / "configmap.yaml",
        manifest_dir / "deployment.yaml",
        manifest_dir / "service.yaml",
    ]
    for path in manifest_paths:
        if not path.exists() or not path.is_file():
            raise SystemExit(f"ERR: Kubernetes manifest missing: {path}")

    record = {
        "kind": "FogStackRuntimeDryRunRecord",
        "schema_version": "v0.1",
        "status": "passed",
        "bundle_id": adapter["bundle_id"],
        "version": adapter["version"],
        "namespace": adapter["namespace"],
        "runtime_adapter_ref": rel(adapter_path),
        "runtime_adapter_digest": sha256_file(adapter_path),
        "node_profile_ref": rel(node_profile_path),
        "node_profile_digest": sha256_file(node_profile_path),
        "agentplane_run": agentplane_run_payload(agentplane_run_id, agentplane_run_ref, agentplane_ref, requested_by),
        "deploy_plan_ref": rel(deploy_plan_path),
        "deploy_plan_digest": sha256_file(deploy_plan_path),
        "cluster_readiness_record_ref": rel(cluster_record_path),
        "cluster_readiness_record_digest": sha256_file(cluster_record_path),
        "gitops_bundle_ref": rel(gitops_bundle_path),
        "gitops_bundle_digest": sha256_file(gitops_bundle_path),
        "gitops_readiness_record_ref": rel(gitops_readiness_path),
        "gitops_readiness_record_digest": sha256_file(gitops_readiness_path),
        "kubernetes_manifests": [
            artifact("kubernetes-configmap", manifest_paths[0]),
            artifact("kubernetes-deployment", manifest_paths[1]),
            artifact("kubernetes-service", manifest_paths[2]),
        ],
        "runtime_policy": adapter["runtime_policy"],
        "dry_run_result": {
            "mode": "dry-run",
            "mutated_cluster": False,
            "validated_inputs": [
                "agentplane_run",
                "runtime_adapter",
                "node_profile",
                "deploy_plan",
                "cluster_readiness_record",
                "gitops_bundle",
                "gitops_readiness_record",
                "kubernetes_manifests",
            ],
            "validation_path": "contract-and-digest-only",
        },
        "artifacts": [
            artifact("runtime-adapter", adapter_path),
            artifact("node-profile", node_profile_path),
            artifact("deploy-plan", deploy_plan_path),
            artifact("cluster-readiness-record", cluster_record_path),
            artifact("gitops-bundle", gitops_bundle_path),
            artifact("gitops-readiness-record", gitops_readiness_path),
            artifact("kubernetes-configmap", manifest_paths[0]),
            artifact("kubernetes-deployment", manifest_paths[1]),
            artifact("kubernetes-service", manifest_paths[2]),
        ],
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a FogStack runtime dry-run record")
    parser.add_argument("--runtime-adapter", required=True, type=Path)
    parser.add_argument("--manifest-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agentplane-run-id", default="agentplane-run:fogstack.access:local-dry-run")
    parser.add_argument("--agentplane-run-ref", default="agentplane://runs/fogstack.access/local-dry-run")
    parser.add_argument("--agentplane-ref", default="github://SocioProphet/agentplane")
    parser.add_argument("--requested-by", default="human:operator")
    args = parser.parse_args()
    record = emit_record(
        args.runtime_adapter,
        args.manifest_dir,
        args.output,
        args.agentplane_run_id,
        args.agentplane_run_ref,
        args.agentplane_ref,
        args.requested_by,
    )
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
