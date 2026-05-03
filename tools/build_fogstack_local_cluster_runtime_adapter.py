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


def build_adapter(
    deploy_plan_path: Path,
    cluster_readiness_path: Path,
    gitops_bundle_path: Path,
    gitops_readiness_path: Path,
    output_path: Path,
    mode: str,
    cluster_provider: str,
    cluster_name: str,
    kubectl_context: str,
) -> dict[str, Any]:
    deploy_plan_path = resolve(deploy_plan_path)
    cluster_readiness_path = resolve(cluster_readiness_path)
    gitops_bundle_path = resolve(gitops_bundle_path)
    gitops_readiness_path = resolve(gitops_readiness_path)
    output_path = resolve(output_path)

    deploy_plan = load_json(deploy_plan_path)
    cluster_readiness = load_json(cluster_readiness_path)
    gitops_bundle = load_json(gitops_bundle_path)
    gitops_readiness = load_json(gitops_readiness_path)

    if deploy_plan.get("kind") != "FogStackDeployPlan":
        raise SystemExit("ERR: expected FogStackDeployPlan")
    if cluster_readiness.get("kind") != "FogStackClusterReadinessRecord":
        raise SystemExit("ERR: expected FogStackClusterReadinessRecord")
    if gitops_bundle.get("kind") != "FogStackGitOpsBundle":
        raise SystemExit("ERR: expected FogStackGitOpsBundle")
    if gitops_readiness.get("kind") != "FogStackGitOpsReadinessRecord":
        raise SystemExit("ERR: expected FogStackGitOpsReadinessRecord")

    bundle_id = deploy_plan["bundle_id"]
    version = deploy_plan["version"]
    namespace = deploy_plan["namespace"]
    for name, data in [("GitOps bundle", gitops_bundle), ("GitOps readiness", gitops_readiness)]:
        if data.get("bundle_id") != bundle_id:
            raise SystemExit(f"ERR: {name} bundle_id does not match deploy plan")
        if data.get("version") != version:
            raise SystemExit(f"ERR: {name} version does not match deploy plan")
    if cluster_readiness.get("status") != "passed":
        raise SystemExit("ERR: cluster readiness record must have passed status")
    if gitops_readiness.get("status") != "passed":
        raise SystemExit("ERR: GitOps readiness record must have passed status")

    supported_tools = ["kubectl"] if cluster_provider == "generic-kubernetes" else ["kubectl", "kind"]
    adapter = {
        "kind": "FogStackLocalClusterRuntimeAdapter",
        "schema_version": "v0.1",
        "bundle_id": bundle_id,
        "version": version,
        "namespace": namespace,
        "adapter": {
            "mode": mode,
            "cluster_provider": cluster_provider,
            "cluster_name": cluster_name,
            "kubectl_context": kubectl_context,
            "supported_tools": supported_tools,
        },
        "inputs": {
            "deploy_plan_ref": rel(deploy_plan_path),
            "deploy_plan_digest": sha256_file(deploy_plan_path),
            "cluster_readiness_record_ref": rel(cluster_readiness_path),
            "cluster_readiness_record_digest": sha256_file(cluster_readiness_path),
            "gitops_bundle_ref": rel(gitops_bundle_path),
            "gitops_bundle_digest": sha256_file(gitops_bundle_path),
            "gitops_readiness_record_ref": rel(gitops_readiness_path),
            "gitops_readiness_record_digest": sha256_file(gitops_readiness_path),
        },
        "runtime_policy": {
            "live_apply_allowed": False,
            "requires_human_approval": True,
            "network_default": "deny",
            "secrets_default": "deny",
        },
        "artifacts": [
            artifact("deploy-plan", deploy_plan_path),
            artifact("cluster-readiness-record", cluster_readiness_path),
            artifact("gitops-bundle", gitops_bundle_path),
            artifact("gitops-readiness-record", gitops_readiness_path),
        ],
    }
    write_json(output_path, adapter)
    return adapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FogStack local cluster runtime adapter contract")
    parser.add_argument("--deploy-plan", required=True, type=Path)
    parser.add_argument("--cluster-readiness-record", required=True, type=Path)
    parser.add_argument("--gitops-bundle", required=True, type=Path)
    parser.add_argument("--gitops-readiness-record", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=["dry-run", "local-cluster"], default="dry-run")
    parser.add_argument("--cluster-provider", choices=["kind", "generic-kubernetes"], default="kind")
    parser.add_argument("--cluster-name", default="fogstack-local")
    parser.add_argument("--kubectl-context", default="kind-fogstack-local")
    args = parser.parse_args()

    adapter = build_adapter(
        deploy_plan_path=args.deploy_plan,
        cluster_readiness_path=args.cluster_readiness_record,
        gitops_bundle_path=args.gitops_bundle,
        gitops_readiness_path=args.gitops_readiness_record,
        output_path=args.output,
        mode=args.mode,
        cluster_provider=args.cluster_provider,
        cluster_name=args.cluster_name,
        kubectl_context=args.kubectl_context,
    )
    print(json.dumps(adapter, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
