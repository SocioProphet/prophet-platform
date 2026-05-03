#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "deploy" / "fogstack-deploy-plan-v0.1.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def validate_schema(plan: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    return [
        f"schema error at {'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.absolute_path))
    ]


def validate_plan(plan_path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    errors: list[str] = []
    plan = load_json(plan_path)

    errors.extend(validate_schema(plan, schema_path))
    if errors:
        return errors

    manifest_ref = plan["manifest_ref"]
    bundle_ref = plan["bundle_ref"]
    agent_corps_ref = plan["agent_corps_plan_ref"]
    manifest_path = path_from_ref(manifest_ref)
    bundle_path = path_from_ref(bundle_ref)
    agent_corps_path = path_from_ref(agent_corps_ref)

    if not manifest_path.exists():
        errors.append(f"manifest_ref missing: {manifest_ref}")
    elif not manifest_path.is_file():
        errors.append(f"manifest_ref is not a file: {manifest_ref}")
    else:
        actual_manifest_digest = sha256_file(manifest_path)
        if actual_manifest_digest != plan["manifest_digest"]:
            errors.append(f"manifest_digest mismatch: {manifest_ref}")

    if not bundle_path.exists():
        errors.append(f"bundle_ref missing: {bundle_ref}")
    elif not bundle_path.is_file():
        errors.append(f"bundle_ref is not a file: {bundle_ref}")
    else:
        actual_bundle_digest = sha256_file(bundle_path)
        if actual_bundle_digest != plan["bundle_digest"]:
            errors.append(f"bundle_digest mismatch: {bundle_ref}")

    if not agent_corps_path.exists():
        errors.append(f"agent_corps_plan_ref missing: {agent_corps_ref}")
    elif not agent_corps_path.is_file():
        errors.append(f"agent_corps_plan_ref is not a file: {agent_corps_ref}")
    else:
        actual_agent_corps_digest = sha256_file(agent_corps_path)
        if actual_agent_corps_digest != plan["agent_corps_plan_digest"]:
            errors.append(f"agent_corps_plan_digest mismatch: {agent_corps_ref}")
        agent_corps_plan = load_json(agent_corps_path)
        if agent_corps_plan.get("kind") != "FogStackAgentCorpsPlan":
            errors.append("agent_corps_plan_ref must point to a FogStackAgentCorpsPlan")
        if agent_corps_plan.get("bundle_id") != plan["bundle_id"]:
            errors.append("Agent Corps plan bundle_id does not match deploy plan")
        if agent_corps_plan.get("version") != plan["version"]:
            errors.append("Agent Corps plan version does not match deploy plan")

    if manifest_path.exists() and manifest_path.is_file():
        manifest = load_json(manifest_path)
        if manifest.get("bundle_id") != plan["bundle_id"]:
            errors.append("manifest bundle_id does not match deploy plan")
        if manifest.get("version") != plan["version"]:
            errors.append("manifest version does not match deploy plan")
        if manifest.get("bundle") != bundle_ref:
            errors.append("manifest bundle ref does not match deploy plan")
        if manifest.get("bundle_digest") != plan["bundle_digest"]:
            errors.append("manifest bundle_digest does not match deploy plan")

    artifact_ids: set[str] = set()
    artifact_refs: set[str] = set()
    for index, artifact in enumerate(plan.get("artifacts", [])):
        artifact_id = artifact["id"]
        artifact_ref = artifact["ref"]
        artifact_digest = artifact["digest"]

        if artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        artifact_ids.add(artifact_id)

        if artifact_ref in artifact_refs:
            errors.append(f"duplicate artifact ref: {artifact_ref}")
        artifact_refs.add(artifact_ref)

        artifact_path = path_from_ref(artifact_ref)
        if not artifact_path.exists():
            errors.append(f"artifact[{index}] missing: {artifact_ref}")
            continue
        if not artifact_path.is_file():
            errors.append(f"artifact[{index}] is not a file: {artifact_ref}")
            continue
        actual_digest = sha256_file(artifact_path)
        if actual_digest != artifact_digest:
            errors.append(f"artifact[{index}] digest mismatch: {artifact_ref}")

    required_artifacts = {
        "bundle": (bundle_ref, plan["bundle_digest"]),
        "manifest": (manifest_ref, plan["manifest_digest"]),
        "agent-corps-plan": (agent_corps_ref, plan["agent_corps_plan_digest"]),
    }
    artifacts_by_id = {artifact["id"]: artifact for artifact in plan.get("artifacts", [])}
    for artifact_id, (expected_ref, expected_digest) in required_artifacts.items():
        artifact = artifacts_by_id.get(artifact_id)
        if artifact is None:
            errors.append(f"required artifact missing from deploy plan: {artifact_id}")
            continue
        if artifact["ref"] != expected_ref:
            errors.append(f"required artifact ref mismatch: {artifact_id}")
        if artifact["digest"] != expected_digest:
            errors.append(f"required artifact digest mismatch: {artifact_id}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a FogStack deploy plan")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, type=Path)
    args = parser.parse_args()

    errors = validate_plan(args.plan, args.schema)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("FogStack deploy plan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
