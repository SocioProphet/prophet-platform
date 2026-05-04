#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
READ_TIMEOUT_SECONDS = 15


MUTATING_VERBS = {"apply", "create", "delete", "patch", "replace", "rollout", "scale", "set", "annotate", "label", "cordon", "drain", "uncordon"}
READ_ONLY_COMMANDS = {
    ("config", "current-context"),
    ("version", "--client"),
    ("cluster-info",),
    ("get", "namespace"),
    ("get", "storageclass"),
    ("api-resources",),
    ("auth", "can-i"),
}


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def resolve_kubectl(kubectl: str) -> str | None:
    if "/" in kubectl:
        path = Path(kubectl)
        return str(path) if path.exists() else None
    return shutil.which(kubectl)


def command_is_allowed(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] in MUTATING_VERBS and args[:2] != ["auth", "can-i"]:
        return False
    return any(tuple(args[: len(prefix)]) == prefix for prefix in READ_ONLY_COMMANDS)


def run_kubectl(kubectl_path: str, args: list[str]) -> dict[str, Any]:
    if not command_is_allowed(args):
        return {
            "args": ["kubectl", *args],
            "status": "denied",
            "returncode": None,
            "stdout": "",
            "stderr": "command denied by read-only preflight allowlist",
        }
    proc = subprocess.run(
        [kubectl_path, *args],
        capture_output=True,
        text=True,
        timeout=READ_TIMEOUT_SECONDS,
    )
    return {
        "args": ["kubectl", *args],
        "status": "passed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def parse_json_output(command: dict[str, Any]) -> dict[str, Any]:
    if command.get("status") != "passed" or not command.get("stdout"):
        return {}
    try:
        data = json.loads(command["stdout"])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_yes(command: dict[str, Any]) -> bool:
    return command.get("status") == "passed" and str(command.get("stdout", "")).strip().lower() == "yes"


def storage_summary(command: dict[str, Any]) -> dict[str, Any]:
    data = parse_json_output(command)
    items = data.get("items", []) if isinstance(data.get("items"), list) else []
    classes = []
    topolvm = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        name = str(metadata.get("name", ""))
        provisioner = str(item.get("provisioner", ""))
        entry = {"name": name, "provisioner": provisioner}
        classes.append(entry)
        if "topolvm" in name.lower() or "topolvm" in provisioner.lower():
            topolvm.append(entry)
    return {
        "storageclass_count": len(classes),
        "storageclasses": classes,
        "topolvm_observed": bool(topolvm),
        "topolvm_storageclasses": topolvm,
    }


def api_resource_summary(command: dict[str, Any]) -> dict[str, Any]:
    resources = [line.strip() for line in str(command.get("stdout", "")).splitlines() if line.strip()]
    lowered = {resource.lower() for resource in resources}
    argo = any("applications.argoproj.io" == resource or resource.endswith(".argoproj.io") for resource in lowered)
    flux = any(resource.endswith(".toolkit.fluxcd.io") for resource in lowered)
    return {
        "resource_count": len(resources),
        "resources": resources,
        "gitops_controller_api_observed": argo or flux,
        "argo_cd_api_observed": argo,
        "flux_api_observed": flux,
    }


def source_artifact(path: Path | None, artifact_id: str) -> dict[str, str] | None:
    if path is None:
        return None
    resolved = resolve(path)
    if not resolved.exists() or not resolved.is_file():
        return {"id": artifact_id, "ref": rel(resolved), "digest": "missing"}
    return {"id": artifact_id, "ref": rel(resolved), "digest": sha256_file(resolved)}


def infer_namespace(namespace: str | None, deploy_plan_path: Path | None) -> str:
    if namespace:
        return namespace
    if deploy_plan_path:
        plan_path = resolve(deploy_plan_path)
        if plan_path.exists():
            plan = load_json(plan_path)
            value = plan.get("namespace")
            if isinstance(value, str) and value:
                return value
    return "fogstack-access"


def build_blocked_record(
    *,
    namespace: str,
    kubectl: str,
    resolved_kubectl: str | None,
    reason: str,
    require_live_cluster: bool,
    source_artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "kind": "FogStackLiveClusterPreflightRecord",
        "schema_version": "v0.1",
        "status": "blocked",
        "reason": reason,
        "namespace": namespace,
        "mode": "read-only-live-preflight",
        "kubectl": {
            "executable": kubectl,
            "available": resolved_kubectl is not None,
            "resolved_path": resolved_kubectl,
        },
        "source_artifacts": source_artifacts,
        "safety": safety_block(),
        "checks": [],
        "read_operations": [],
        "errors": [reason] if require_live_cluster else [],
    }


def safety_block() -> dict[str, Any]:
    return {
        "mutation_mode": "read-only",
        "mutated_cluster": False,
        "applied_resources": False,
        "created_resources": False,
        "deleted_resources": False,
        "live_apply_allowed": False,
        "human_approval_required_for_apply": True,
        "allowed_command_families": ["config current-context", "version --client", "cluster-info", "get", "api-resources", "auth can-i"],
        "denied_command_families": sorted(MUTATING_VERBS),
    }


def emit_record(
    *,
    output_path: Path,
    namespace: str,
    kubectl: str,
    require_live_cluster: bool,
    deploy_plan: Path | None,
    node_profile: Path | None,
    gitops_bundle: Path | None,
) -> dict[str, Any]:
    source_artifacts = [
        artifact
        for artifact in [
            source_artifact(deploy_plan, "deploy-plan"),
            source_artifact(node_profile, "node-profile"),
            source_artifact(gitops_bundle, "gitops-bundle"),
        ]
        if artifact is not None
    ]
    resolved_kubectl = resolve_kubectl(kubectl)
    if resolved_kubectl is None:
        record = build_blocked_record(
            namespace=namespace,
            kubectl=kubectl,
            resolved_kubectl=None,
            reason="kubectl unavailable; live cluster preflight not attempted",
            require_live_cluster=require_live_cluster,
            source_artifacts=source_artifacts,
        )
        write_json(output_path, record)
        return record

    operations: list[dict[str, Any]] = []

    def run(args: list[str]) -> dict[str, Any]:
        command = run_kubectl(resolved_kubectl, args)
        operations.append({key: command[key] for key in ["args", "status", "returncode"]})
        return command

    current_context = run(["config", "current-context"])
    client_version = run(["version", "--client", "-o", "json"])
    cluster_info = run(["cluster-info"])
    if cluster_info.get("status") != "passed":
        reason = "cluster-info failed; live cluster unavailable or kubeconfig not usable"
        record = build_blocked_record(
            namespace=namespace,
            kubectl=kubectl,
            resolved_kubectl=resolved_kubectl,
            reason=reason,
            require_live_cluster=require_live_cluster,
            source_artifacts=source_artifacts,
        )
        record["read_operations"] = operations
        record["kubectl"]["current_context"] = current_context.get("stdout")
        record["kubectl"]["cluster_info_error"] = cluster_info.get("stderr") or cluster_info.get("stdout")
        write_json(output_path, record)
        return record

    namespace_get = run(["get", "namespace", namespace, "-o", "json"])
    storageclasses = run(["get", "storageclass", "-o", "json"])
    api_resources = run(["api-resources", "-o", "name"])
    can_get_pods = run(["auth", "can-i", "get", "pods", "--namespace", namespace])
    can_list_pods = run(["auth", "can-i", "list", "pods", "--namespace", namespace])
    can_create_deployments = run(["auth", "can-i", "create", "deployments", "--namespace", namespace])
    can_update_deployments = run(["auth", "can-i", "update", "deployments", "--namespace", namespace])
    can_patch_deployments = run(["auth", "can-i", "patch", "deployments", "--namespace", namespace])

    ns = parse_json_output(namespace_get)
    storage = storage_summary(storageclasses)
    resources = api_resource_summary(api_resources)
    authorization = {
        "can_get_pods": parse_yes(can_get_pods),
        "can_list_pods": parse_yes(can_list_pods),
        "can_create_deployments": parse_yes(can_create_deployments),
        "can_update_deployments": parse_yes(can_update_deployments),
        "can_patch_deployments": parse_yes(can_patch_deployments),
        "mutation_permissions_observed_by_sar_only": any(
            parse_yes(command) for command in [can_create_deployments, can_update_deployments, can_patch_deployments]
        ),
    }
    checks = [
        {"id": "kubectl_available", "status": "passed"},
        {"id": "current_context", "status": "passed" if current_context.get("status") == "passed" else "failed"},
        {"id": "cluster_reachable", "status": "passed"},
        {"id": "namespace_exists", "status": "passed" if namespace_get.get("status") == "passed" and ns.get("metadata", {}).get("name") == namespace else "failed"},
        {"id": "storageclasses_readable", "status": "passed" if storageclasses.get("status") == "passed" else "failed"},
        {"id": "readonly_pod_access", "status": "passed" if authorization["can_get_pods"] and authorization["can_list_pods"] else "failed"},
        {"id": "api_resources_readable", "status": "passed" if api_resources.get("status") == "passed" else "failed"},
    ]
    status = "passed" if all(check["status"] == "passed" for check in checks) else "failed"
    errors = [check["id"] for check in checks if check["status"] != "passed"]
    record = {
        "kind": "FogStackLiveClusterPreflightRecord",
        "schema_version": "v0.1",
        "status": status,
        "reason": None if status == "passed" else "one or more read-only live preflight checks failed",
        "namespace": namespace,
        "mode": "read-only-live-preflight",
        "kubectl": {
            "executable": kubectl,
            "available": True,
            "resolved_path": resolved_kubectl,
            "current_context": current_context.get("stdout"),
            "client_version": parse_json_output(client_version),
        },
        "source_artifacts": source_artifacts,
        "safety": safety_block(),
        "cluster": {
            "namespace": ns.get("metadata", {}),
            "storage": storage,
            "api_resources": resources,
            "authorization": authorization,
        },
        "checks": checks,
        "read_operations": operations,
        "errors": errors,
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a non-mutating FogStack live cluster preflight record")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--namespace")
    parser.add_argument("--deploy-plan", type=Path)
    parser.add_argument("--node-profile", type=Path)
    parser.add_argument("--gitops-bundle", type=Path)
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--require-live-cluster", action="store_true")
    args = parser.parse_args()

    namespace = infer_namespace(args.namespace, args.deploy_plan)
    output = resolve(args.output)
    record = emit_record(
        output_path=output,
        namespace=namespace,
        kubectl=args.kubectl,
        require_live_cluster=args.require_live_cluster,
        deploy_plan=args.deploy_plan,
        node_profile=args.node_profile,
        gitops_bundle=args.gitops_bundle,
    )
    print(json.dumps(record, indent=2))
    if record["status"] == "failed" or (record["status"] == "blocked" and args.require_live_cluster):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
