#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
LABEL_PREFIX = "fogstack.socioprophet.io"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def DNS_label(value: str) -> str:
    return value.replace(".", "-").replace("_", "-").lower()


def common_labels(plan: dict[str, Any]) -> dict[str, str]:
    return {
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
        f"{LABEL_PREFIX}/version": plan["version"],
        f"{LABEL_PREFIX}/profile": plan["profile"],
        f"{LABEL_PREFIX}/target": plan["target"],
        f"{LABEL_PREFIX}/agent-corps": "enabled",
    }


def common_annotations(plan: dict[str, Any]) -> dict[str, str]:
    return {
        f"{LABEL_PREFIX}/manifest-ref": plan["manifest_ref"],
        f"{LABEL_PREFIX}/manifest-digest": plan["manifest_digest"],
        f"{LABEL_PREFIX}/bundle-ref": plan["bundle_ref"],
        f"{LABEL_PREFIX}/bundle-digest": plan["bundle_digest"],
        f"{LABEL_PREFIX}/agent-corps-plan-ref": plan["agent_corps_plan_ref"],
        f"{LABEL_PREFIX}/agent-corps-plan-digest": plan["agent_corps_plan_digest"],
    }


def render_config_map(plan: dict[str, Any], name: str, labels: dict[str, str], annotations: dict[str, str]) -> dict[str, Any]:
    components = ",".join(component["id"] for component in plan["runtime"]["components"])
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{name}-config",
            "namespace": plan["namespace"],
            "labels": labels,
            "annotations": annotations,
        },
        "data": {
            "bundle_id": plan["bundle_id"],
            "version": plan["version"],
            "profile": plan["profile"],
            "target": plan["target"],
            "runtime_substrate": plan["runtime"]["substrate"],
            "runtime_components": components,
            "health_endpoint": plan["deployment"]["health_endpoint"],
            "agent_corps_plan_ref": plan["agent_corps_plan_ref"],
            "agent_corps_plan_digest": plan["agent_corps_plan_digest"],
        },
    }


def render_deployment(plan: dict[str, Any], name: str, labels: dict[str, str], annotations: dict[str, str], image: str, port: int) -> dict[str, Any]:
    selector = {
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/part-of": "fogstack",
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
    }
    pod_labels = labels | selector
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": plan["namespace"],
            "labels": labels | {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "fogstack"},
            "annotations": annotations,
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": selector},
            "template": {
                "metadata": {
                    "labels": pod_labels,
                    "annotations": annotations,
                },
                "spec": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [{"name": "http", "containerPort": port}],
                            "envFrom": [{"configMapRef": {"name": f"{name}-config"}}],
                            "readinessProbe": {
                                "httpGet": {"path": plan["deployment"]["health_endpoint"], "port": "http"},
                                "initialDelaySeconds": 3,
                                "periodSeconds": 10,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": plan["deployment"]["health_endpoint"], "port": "http"},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 20,
                            },
                        }
                    ]
                },
            },
        },
    }


def render_service(plan: dict[str, Any], name: str, labels: dict[str, str], annotations: dict[str, str], port: int) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": plan["namespace"],
            "labels": labels | {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "fogstack"},
            "annotations": annotations,
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/part-of": "fogstack",
                f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
            },
            "ports": [{"name": "http", "port": port, "targetPort": "http"}],
        },
    }


def render_manifests(plan: dict[str, Any], image: str, port: int) -> dict[str, dict[str, Any]]:
    if plan.get("kind") != "FogStackDeployPlan":
        raise SystemExit("ERR: expected FogStackDeployPlan")
    if not plan.get("agent_corps_plan_ref") or not plan.get("agent_corps_plan_digest"):
        raise SystemExit("ERR: deploy plan must include Agent Corps plan ref and digest")

    name = DNS_label(plan["bundle_id"])
    labels = common_labels(plan)
    annotations = common_annotations(plan)
    return {
        "configmap.yaml": render_config_map(plan, name, labels, annotations),
        "deployment.yaml": render_deployment(plan, name, labels, annotations, image, port),
        "service.yaml": render_service(plan, name, labels, annotations, port),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Kubernetes manifests from a FogStack deploy plan")
    parser.add_argument("--deploy-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--image", default="ghcr.io/socioprophet/fogstack-access:0.1.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    deploy_plan_path = args.deploy_plan if args.deploy_plan.is_absolute() else ROOT / args.deploy_plan
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifests = render_manifests(load_json(deploy_plan_path), args.image, args.port)
    for filename, manifest in manifests.items():
        (output_dir / filename).write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(json.dumps({"kind": "FogStackKubernetesManifestSet", "output_dir": str(output_dir), "files": sorted(manifests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
