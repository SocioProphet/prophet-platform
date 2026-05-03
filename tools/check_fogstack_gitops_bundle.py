#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "gitops" / "fogstack-gitops-bundle-v0.1.schema.json"
LABEL_PREFIX = "fogstack.socioprophet.io"


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


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def schema_errors(bundle: dict[str, Any], schema_path: Path) -> list[str]:
    validator = Draft202012Validator(load_json(schema_path))
    return [
        f"schema error at {'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(bundle), key=lambda item: list(item.absolute_path))
    ]


def check_artifact(artifact: dict[str, Any], errors: list[str]) -> None:
    ref = artifact["ref"]
    path = path_from_ref(ref)
    if not path.exists():
        errors.append(f"artifact missing: {artifact['id']} {ref}")
        return
    if not path.is_file():
        errors.append(f"artifact is not a file: {artifact['id']} {ref}")
        return
    actual = sha256_file(path)
    if actual != artifact["digest"]:
        errors.append(f"artifact digest mismatch: {artifact['id']} {ref}")


def validate_bundle(bundle_path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    errors: list[str] = []
    bundle = load_json(bundle_path)
    errors.extend(schema_errors(bundle, schema_path))
    if errors:
        return errors

    for artifact in bundle["artifacts"]:
        check_artifact(artifact, errors)
    for manifest in bundle["manifests"]:
        check_artifact(manifest, errors)

    artifacts_by_id = {artifact["id"]: artifact for artifact in bundle["artifacts"]}
    required_ids = {"deploy-plan", "agent-corps-plan", "application", "kustomization", "configmap", "deployment", "service"}
    missing_ids = sorted(required_ids - set(artifacts_by_id))
    for artifact_id in missing_ids:
        errors.append(f"required artifact missing: {artifact_id}")

    deploy_plan_path = path_from_ref(bundle["deploy_plan_ref"])
    if not deploy_plan_path.exists():
        errors.append(f"deploy plan missing: {bundle['deploy_plan_ref']}")
    else:
        if sha256_file(deploy_plan_path) != bundle["deploy_plan_digest"]:
            errors.append("deploy plan digest mismatch")
        deploy_plan = load_json(deploy_plan_path)
        if deploy_plan.get("kind") != "FogStackDeployPlan":
            errors.append("deploy plan kind mismatch")
        if deploy_plan.get("bundle_id") != bundle["bundle_id"]:
            errors.append("deploy plan bundle_id mismatch")
        if deploy_plan.get("version") != bundle["version"]:
            errors.append("deploy plan version mismatch")
        if deploy_plan.get("namespace") != bundle["namespace"]:
            errors.append("deploy plan namespace mismatch")
        if deploy_plan.get("agent_corps_plan_ref") != bundle["agent_corps_plan_ref"]:
            errors.append("Agent Corps plan ref mismatch")
        if deploy_plan.get("agent_corps_plan_digest") != bundle["agent_corps_plan_digest"]:
            errors.append("Agent Corps plan digest mismatch")

    agent_corps_path = path_from_ref(bundle["agent_corps_plan_ref"])
    if not agent_corps_path.exists():
        errors.append(f"Agent Corps plan missing: {bundle['agent_corps_plan_ref']}")
    else:
        if sha256_file(agent_corps_path) != bundle["agent_corps_plan_digest"]:
            errors.append("Agent Corps artifact digest mismatch")
        agent_corps = load_json(agent_corps_path)
        if agent_corps.get("kind") != "FogStackAgentCorpsPlan":
            errors.append("Agent Corps kind mismatch")
        if agent_corps.get("bundle_id") != bundle["bundle_id"]:
            errors.append("Agent Corps bundle_id mismatch")
        if agent_corps.get("version") != bundle["version"]:
            errors.append("Agent Corps version mismatch")

    application = load_yaml(path_from_ref(bundle["application"]["ref"]))
    if application.get("kind") != "Application":
        errors.append("Application kind mismatch")
    metadata = application.get("metadata", {})
    labels = metadata.get("labels", {})
    annotations = metadata.get("annotations", {})
    if labels.get(f"{LABEL_PREFIX}/bundle-id") != bundle["bundle_id"]:
        errors.append("Application bundle label mismatch")
    if labels.get(f"{LABEL_PREFIX}/agent-corps") != "enabled":
        errors.append("Application Agent Corps label missing")
    if annotations.get(f"{LABEL_PREFIX}/deploy-plan-digest") != bundle["deploy_plan_digest"]:
        errors.append("Application deploy-plan digest annotation mismatch")
    if annotations.get(f"{LABEL_PREFIX}/agent-corps-plan-digest") != bundle["agent_corps_plan_digest"]:
        errors.append("Application Agent Corps digest annotation mismatch")
    spec = application.get("spec", {})
    source = spec.get("source", {})
    destination = spec.get("destination", {})
    if source.get("repoURL") != bundle["source"]["repo_url"]:
        errors.append("Application repoURL mismatch")
    if source.get("targetRevision") != bundle["source"]["target_revision"]:
        errors.append("Application targetRevision mismatch")
    if source.get("path") != bundle["source"]["path"]:
        errors.append("Application path mismatch")
    if destination.get("namespace") != bundle["namespace"]:
        errors.append("Application destination namespace mismatch")

    kustomization = load_yaml(path_from_ref(bundle["kustomization"]["ref"]))
    if kustomization.get("kind") != "Kustomization":
        errors.append("Kustomization kind mismatch")
    if kustomization.get("namespace") != bundle["namespace"]:
        errors.append("Kustomization namespace mismatch")
    resources = kustomization.get("resources")
    expected_resources = ["manifests/configmap.yaml", "manifests/deployment.yaml", "manifests/service.yaml"]
    if resources != expected_resources:
        errors.append("Kustomization resources mismatch")
    common_labels = kustomization.get("commonLabels", {})
    if common_labels.get(f"{LABEL_PREFIX}/bundle-id") != bundle["bundle_id"]:
        errors.append("Kustomization bundle label mismatch")
    if common_labels.get(f"{LABEL_PREFIX}/agent-corps") != "enabled":
        errors.append("Kustomization Agent Corps label missing")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a FogStack GitOps bundle")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, type=Path)
    args = parser.parse_args()

    bundle_path = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    schema_path = args.schema if args.schema.is_absolute() else ROOT / args.schema
    errors = validate_bundle(bundle_path, schema_path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("FogStack GitOps bundle passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
