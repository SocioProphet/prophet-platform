#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
LABEL_PREFIX = "fogstack.socioprophet.io"
DISCOVERY_FAILURE_MARKERS = (
    "couldn't get current server API group list",
    "the server could not find the requested resource",
    "connection refused",
    "unable to recognize",
    "no configuration has been provided",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML object in {path}")
    return data


def dns_label(value: str) -> str:
    return value.replace(".", "-").replace("_", "-").lower()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def required_labels(plan: dict[str, Any]) -> dict[str, str]:
    return {
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
        f"{LABEL_PREFIX}/version": plan["version"],
        f"{LABEL_PREFIX}/profile": plan["profile"],
        f"{LABEL_PREFIX}/target": plan["target"],
        f"{LABEL_PREFIX}/agent-corps": "enabled",
    }


def required_annotations(plan: dict[str, Any]) -> dict[str, str]:
    return {
        f"{LABEL_PREFIX}/manifest-ref": plan["manifest_ref"],
        f"{LABEL_PREFIX}/manifest-digest": plan["manifest_digest"],
        f"{LABEL_PREFIX}/bundle-ref": plan["bundle_ref"],
        f"{LABEL_PREFIX}/bundle-digest": plan["bundle_digest"],
        f"{LABEL_PREFIX}/agent-corps-plan-ref": plan["agent_corps_plan_ref"],
        f"{LABEL_PREFIX}/agent-corps-plan-digest": plan["agent_corps_plan_digest"],
    }


def require_mapping(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{path} must be an object")
    return {}


def check_labels(resource: dict[str, Any], plan: dict[str, Any], resource_name: str, errors: list[str]) -> None:
    metadata = require_mapping(resource.get("metadata"), f"{resource_name}.metadata", errors)
    labels = require_mapping(metadata.get("labels"), f"{resource_name}.metadata.labels", errors)
    for key, expected in required_labels(plan).items():
        if labels.get(key) != expected:
            errors.append(f"{resource_name} label mismatch: {key}")


def check_annotations(resource: dict[str, Any], plan: dict[str, Any], resource_name: str, errors: list[str]) -> None:
    metadata = require_mapping(resource.get("metadata"), f"{resource_name}.metadata", errors)
    annotations = require_mapping(metadata.get("annotations"), f"{resource_name}.metadata.annotations", errors)
    for key, expected in required_annotations(plan).items():
        if annotations.get(key) != expected:
            errors.append(f"{resource_name} annotation mismatch: {key}")


def validate_manifests(deploy_plan_path: Path, manifest_dir: Path) -> list[str]:
    errors: list[str] = []
    plan = load_json(deploy_plan_path)
    expected_name = dns_label(plan["bundle_id"])
    namespace = plan["namespace"]
    health_endpoint = plan["deployment"]["health_endpoint"]

    try:
        configmap = load_yaml(manifest_dir / "configmap.yaml")
        deployment = load_yaml(manifest_dir / "deployment.yaml")
        service = load_yaml(manifest_dir / "service.yaml")
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]

    expected = [
        (configmap, "ConfigMap", f"{expected_name}-config", "configmap"),
        (deployment, "Deployment", expected_name, "deployment"),
        (service, "Service", expected_name, "service"),
    ]
    for resource, kind, name, resource_name in expected:
        if resource.get("kind") != kind:
            errors.append(f"{resource_name} kind mismatch")
        metadata = require_mapping(resource.get("metadata"), f"{resource_name}.metadata", errors)
        if metadata.get("name") != name:
            errors.append(f"{resource_name} name mismatch")
        if metadata.get("namespace") != namespace:
            errors.append(f"{resource_name} namespace mismatch")
        check_labels(resource, plan, resource_name, errors)
        check_annotations(resource, plan, resource_name, errors)

    config_data = require_mapping(configmap.get("data"), "configmap.data", errors)
    for key, expected_value in {
        "bundle_id": plan["bundle_id"],
        "version": plan["version"],
        "profile": plan["profile"],
        "target": plan["target"],
        "health_endpoint": health_endpoint,
        "agent_corps_plan_ref": plan["agent_corps_plan_ref"],
        "agent_corps_plan_digest": plan["agent_corps_plan_digest"],
    }.items():
        if config_data.get(key) != expected_value:
            errors.append(f"configmap data mismatch: {key}")

    deployment_spec = require_mapping(deployment.get("spec"), "deployment.spec", errors)
    template = require_mapping(deployment_spec.get("template"), "deployment.spec.template", errors)
    pod_metadata = require_mapping(template.get("metadata"), "deployment.spec.template.metadata", errors)
    pod_labels = require_mapping(pod_metadata.get("labels"), "deployment.spec.template.metadata.labels", errors)
    if pod_labels.get(f"{LABEL_PREFIX}/bundle-id") != plan["bundle_id"]:
        errors.append("deployment pod bundle label mismatch")
    if pod_labels.get(f"{LABEL_PREFIX}/agent-corps") != "enabled":
        errors.append("deployment pod Agent Corps label missing")

    pod_spec = require_mapping(template.get("spec"), "deployment.spec.template.spec", errors)
    containers = pod_spec.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(containers[0], dict):
        errors.append("deployment must define exactly one container")
        container: dict[str, Any] = {}
    else:
        container = containers[0]
    if container.get("name") != expected_name:
        errors.append("deployment container name mismatch")
    if container.get("envFrom") != [{"configMapRef": {"name": f"{expected_name}-config"}}]:
        errors.append("deployment container envFrom mismatch")
    for probe_name in ["readinessProbe", "livenessProbe"]:
        probe = require_mapping(container.get(probe_name), f"container.{probe_name}", errors)
        http_get = require_mapping(probe.get("httpGet"), f"container.{probe_name}.httpGet", errors)
        if http_get.get("path") != health_endpoint or http_get.get("port") != "http":
            errors.append(f"deployment {probe_name} mismatch")

    service_spec = require_mapping(service.get("spec"), "service.spec", errors)
    selector = require_mapping(service_spec.get("selector"), "service.spec.selector", errors)
    expected_selector = {
        "app.kubernetes.io/name": expected_name,
        "app.kubernetes.io/part-of": "fogstack",
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
    }
    if selector != expected_selector:
        errors.append("service selector mismatch")
    ports = service_spec.get("ports")
    if not isinstance(ports, list) or not ports:
        errors.append("service ports missing")
    else:
        first_port = ports[0]
        if not isinstance(first_port, dict) or first_port.get("name") != "http" or first_port.get("targetPort") != "http":
            errors.append("service http port mismatch")

    return errors


def resolve_kubectl(kubectl: str) -> str | None:
    if "/" in kubectl:
        path = Path(kubectl)
        return str(path) if path.exists() else None
    return shutil.which(kubectl)


def is_discovery_failure(details: str) -> bool:
    lowered = details.lower()
    return any(marker in lowered for marker in DISCOVERY_FAILURE_MARKERS)


def run_kubectl_dry_run(manifest_dir: Path, kubectl: str, require_kubectl: bool) -> dict[str, Any]:
    resolved = resolve_kubectl(kubectl)
    result: dict[str, Any] = {
        "requested": True,
        "required": require_kubectl,
        "executable": kubectl,
        "available": resolved is not None,
        "resolved_path": resolved,
        "dry_run_status": "not_run",
        "fallback_mode": None,
        "message": None,
        "errors": [],
    }
    if resolved is None:
        result["dry_run_status"] = "failed" if require_kubectl else "fallback"
        result["fallback_mode"] = None if require_kubectl else "offline_validation"
        result["message"] = "kubectl required but unavailable" if require_kubectl else "kubectl unavailable; offline validation used"
        if require_kubectl:
            result["errors"].append(f"kubectl not found: {kubectl}")
        return result

    proc = subprocess.run(
        [resolved, "apply", "--dry-run=client", "--validate=false", "-f", str(manifest_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout).strip()
        if not require_kubectl and is_discovery_failure(details):
            result["dry_run_status"] = "fallback"
            result["fallback_mode"] = "offline_validation"
            result["message"] = "kubectl dry-run unavailable; offline validation used"
            return result
        result["dry_run_status"] = "failed"
        result["message"] = "kubectl dry-run failed"
        result["errors"].append(f"kubectl dry-run failed: {details}")
        return result

    result["dry_run_status"] = "passed"
    result["message"] = "kubectl dry-run passed"
    return result


def build_readiness_record(
    deploy_plan_path: Path,
    manifest_dir: Path,
    offline_errors: list[str],
    kubectl_result: dict[str, Any],
) -> dict[str, Any]:
    status = "failed" if offline_errors or kubectl_result.get("errors") else "passed"
    if kubectl_result["dry_run_status"] == "passed":
        validation_path = "offline+kubectl-dry-run"
    elif kubectl_result["dry_run_status"] == "fallback":
        validation_path = "offline-fallback"
    elif kubectl_result["dry_run_status"] == "not_requested":
        validation_path = "offline"
    else:
        validation_path = "failed"
    return {
        "kind": "FogStackClusterReadinessRecord",
        "schema_version": "v0.1",
        "status": status,
        "deploy_plan_ref": rel(deploy_plan_path),
        "manifest_dir": rel(manifest_dir),
        "validation_path": validation_path,
        "offline_validation": {
            "status": "failed" if offline_errors else "passed",
            "errors": offline_errors,
        },
        "kubectl": {key: value for key, value in kubectl_result.items() if key != "errors"},
        "errors": [*offline_errors, *kubectl_result.get("errors", [])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check rendered FogStack Kubernetes manifests")
    parser.add_argument("--deploy-plan", required=True, type=Path)
    parser.add_argument("--manifest-dir", required=True, type=Path)
    parser.add_argument("--kubectl-dry-run", action="store_true", help="Also attempt kubectl apply --dry-run=client when kubectl is available")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable name or path")
    parser.add_argument("--require-kubectl", action="store_true", help="Fail if --kubectl-dry-run is requested and kubectl is unavailable")
    parser.add_argument("--record-output", type=Path, help="Write a FogStackClusterReadinessRecord JSON artifact")
    args = parser.parse_args()

    deploy_plan_path = args.deploy_plan if args.deploy_plan.is_absolute() else ROOT / args.deploy_plan
    manifest_dir = args.manifest_dir if args.manifest_dir.is_absolute() else ROOT / args.manifest_dir
    offline_errors = validate_manifests(deploy_plan_path, manifest_dir)
    kubectl_result = {
        "requested": args.kubectl_dry_run,
        "required": args.require_kubectl,
        "executable": args.kubectl,
        "available": False,
        "resolved_path": None,
        "dry_run_status": "not_requested",
        "fallback_mode": None,
        "message": "kubectl dry-run not requested",
        "errors": [],
    }
    status_lines = ["offline validation passed"] if not offline_errors else []
    if not offline_errors and args.kubectl_dry_run:
        kubectl_result = run_kubectl_dry_run(manifest_dir, args.kubectl, args.require_kubectl)
        if kubectl_result["message"]:
            status_lines.append(kubectl_result["message"])

    record = build_readiness_record(deploy_plan_path, manifest_dir, offline_errors, kubectl_result)
    if args.record_output:
        output = args.record_output if args.record_output.is_absolute() else ROOT / args.record_output
        write_json(output, record)

    if record["errors"]:
        for error in record["errors"]:
            print(error, file=sys.stderr)
        return 1

    print("FogStack Kubernetes manifests passed.")
    for line in status_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
