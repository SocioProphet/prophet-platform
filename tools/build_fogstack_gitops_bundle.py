#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


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


def dns_label(value: str) -> str:
    return value.replace(".", "-").replace("_", "-").lower()


def copy_manifest(src: Path, dst: Path) -> dict[str, str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return {"id": dst.stem, "ref": rel(dst), "digest": sha256_file(dst)}


def render_application(plan: dict[str, Any], name: str, repo_url: str, target_revision: str, path: str) -> dict[str, Any]:
    labels = {
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
        f"{LABEL_PREFIX}/version": plan["version"],
        f"{LABEL_PREFIX}/agent-corps": "enabled",
    }
    annotations = {
        f"{LABEL_PREFIX}/deploy-plan-ref": plan["deploy_plan_ref"] if "deploy_plan_ref" in plan else "",
        f"{LABEL_PREFIX}/deploy-plan-digest": plan["deploy_plan_digest"] if "deploy_plan_digest" in plan else "",
        f"{LABEL_PREFIX}/agent-corps-plan-ref": plan["agent_corps_plan_ref"],
        f"{LABEL_PREFIX}/agent-corps-plan-digest": plan["agent_corps_plan_digest"],
    }
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": name,
            "namespace": "argocd",
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": repo_url,
                "targetRevision": target_revision,
                "path": path,
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": plan["namespace"],
            },
            "syncPolicy": {
                "automated": None,
                "syncOptions": ["CreateNamespace=true"],
            },
        },
    }


def render_kustomization(resources: list[str], namespace: str, labels: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "namespace": namespace,
        "resources": resources,
        "commonLabels": labels,
    }


def build_bundle(
    deploy_plan_path: Path,
    manifest_dir: Path,
    output_dir: Path,
    repo_url: str,
    target_revision: str,
    gitops_path: str,
) -> dict[str, Any]:
    deploy_plan_path = deploy_plan_path if deploy_plan_path.is_absolute() else ROOT / deploy_plan_path
    manifest_dir = manifest_dir if manifest_dir.is_absolute() else ROOT / manifest_dir
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = load_json(deploy_plan_path)
    if plan.get("kind") != "FogStackDeployPlan":
        raise SystemExit("ERR: expected FogStackDeployPlan")

    name = dns_label(plan["bundle_id"])
    manifests_dir = output_dir / "manifests"
    copied = [
        copy_manifest(manifest_dir / "configmap.yaml", manifests_dir / "configmap.yaml"),
        copy_manifest(manifest_dir / "deployment.yaml", manifests_dir / "deployment.yaml"),
        copy_manifest(manifest_dir / "service.yaml", manifests_dir / "service.yaml"),
    ]

    common_labels = {
        f"{LABEL_PREFIX}/bundle-id": plan["bundle_id"],
        f"{LABEL_PREFIX}/version": plan["version"],
        f"{LABEL_PREFIX}/agent-corps": "enabled",
    }
    kustomization_path = output_dir / "kustomization.yaml"
    application_path = output_dir / "application.yaml"
    bundle_path = output_dir / "gitops-bundle.json"

    render_kustomization_payload = render_kustomization(
        ["manifests/configmap.yaml", "manifests/deployment.yaml", "manifests/service.yaml"],
        plan["namespace"],
        common_labels,
    )
    write_yaml(kustomization_path, render_kustomization_payload)
    write_yaml(application_path, render_application(plan | {"deploy_plan_ref": rel(deploy_plan_path), "deploy_plan_digest": sha256_file(deploy_plan_path)}, name, repo_url, target_revision, gitops_path))

    artifacts = [
        {"id": "deploy-plan", "ref": rel(deploy_plan_path), "digest": sha256_file(deploy_plan_path)},
        {"id": "agent-corps-plan", "ref": plan["agent_corps_plan_ref"], "digest": plan["agent_corps_plan_digest"]},
        {"id": "application", "ref": rel(application_path), "digest": sha256_file(application_path)},
        {"id": "kustomization", "ref": rel(kustomization_path), "digest": sha256_file(kustomization_path)},
        *copied,
    ]
    bundle = {
        "kind": "FogStackGitOpsBundle",
        "schema_version": "v0.1",
        "bundle_id": plan["bundle_id"],
        "version": plan["version"],
        "namespace": plan["namespace"],
        "deploy_plan_ref": rel(deploy_plan_path),
        "deploy_plan_digest": sha256_file(deploy_plan_path),
        "agent_corps_plan_ref": plan["agent_corps_plan_ref"],
        "agent_corps_plan_digest": plan["agent_corps_plan_digest"],
        "source": {
            "repo_url": repo_url,
            "target_revision": target_revision,
            "path": gitops_path,
        },
        "application": {
            "name": name,
            "ref": rel(application_path),
            "digest": sha256_file(application_path),
        },
        "kustomization": {
            "ref": rel(kustomization_path),
            "digest": sha256_file(kustomization_path),
        },
        "manifests": copied,
        "artifacts": artifacts,
    }
    write_json(bundle_path, bundle)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FogStack GitOps bundle from a deploy plan and rendered manifests")
    parser.add_argument("--deploy-plan", required=True, type=Path)
    parser.add_argument("--manifest-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repo-url", default="https://github.com/SocioProphet/prophet-platform.git")
    parser.add_argument("--target-revision", default="main")
    parser.add_argument("--gitops-path", default="build/fogstack-gitops")
    args = parser.parse_args()

    bundle = build_bundle(args.deploy_plan, args.manifest_dir, args.output_dir, args.repo_url, args.target_revision, args.gitops_path)
    print(json.dumps(bundle, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
