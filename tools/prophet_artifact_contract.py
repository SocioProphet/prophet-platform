#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_API_VERSION = "socioprophet.org/v1alpha1"
SUPPORTED_KIND = "ProphetArtifact"
STANDARD_VERBS = [
    "detect",
    "fetch",
    "prepare",
    "build",
    "run",
    "validate",
    "benchmark",
    "tune",
    "publish",
    "attest",
]
EXPECTED_EVIDENCE_FILES = [
    "run-record.json",
    "checksums.json",
    "validation-report.json",
    "benchmark-report.json",
    "sociosphere-registration.json",
    "sherlock-index-payload.json",
    "delivery-excellence-scoreboard-payload.json",
]


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _as_object(value: Any, where: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{where} must be an object")
    return value


def _as_list(value: Any, where: str) -> list[Any]:
    require(isinstance(value, list), f"{where} must be a list")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing artifact manifest: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid YAML in artifact manifest: {exc}") from exc
    require(isinstance(parsed, dict), "manifest root must be a YAML object")
    return parsed


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    require(manifest.get("apiVersion") == SUPPORTED_API_VERSION, f"apiVersion must be {SUPPORTED_API_VERSION}")
    require(manifest.get("kind") == SUPPORTED_KIND, f"kind must be {SUPPORTED_KIND}")

    metadata = _as_object(manifest.get("metadata"), "metadata")
    require(isinstance(metadata.get("name"), str) and metadata["name"], "metadata.name is required")
    require(isinstance(metadata.get("version"), str) and metadata["version"], "metadata.version is required")

    actions = _as_list(manifest.get("actions"), "actions")
    require(actions, "actions must include at least one action")
    seen_verbs: set[str] = set()
    for idx, action in enumerate(actions):
        action_obj = _as_object(action, f"actions[{idx}]")
        require(isinstance(action_obj.get("id"), str) and action_obj["id"], f"actions[{idx}].id is required")
        verb = action_obj.get("verb")
        require(isinstance(verb, str) and verb in STANDARD_VERBS, f"actions[{idx}].verb must be one of: {', '.join(STANDARD_VERBS)}")
        require(verb not in seen_verbs, f"actions[{idx}].verb duplicate: {verb}")
        seen_verbs.add(verb)
        if "privileged" in action_obj:
            require(isinstance(action_obj["privileged"], bool), f"actions[{idx}].privileged must be a boolean")
        mode = action_obj.get("mode", "noop")
        require(mode in {"noop", "fixture"}, f"actions[{idx}].mode must be 'noop' or 'fixture'")

    provenance = _as_object(manifest.get("provenance"), "provenance")
    require(isinstance(provenance.get("sourceUri"), str) and provenance["sourceUri"], "provenance.sourceUri is required")
    require(isinstance(provenance.get("license"), str) and provenance["license"], "provenance.license is required")
    _as_list(provenance.get("receipts", []), "provenance.receipts")

    policy = _as_object(manifest.get("policy"), "policy")
    require(isinstance(policy.get("safetyClass"), str) and policy["safetyClass"], "policy.safetyClass is required")
    require(isinstance(policy.get("network"), str) and policy["network"], "policy.network is required")
    require(isinstance(policy.get("allowPrivilegedActions"), bool), "policy.allowPrivilegedActions is required and must be boolean")

    evidence = _as_object(manifest.get("evidence"), "evidence")
    required_outputs = _as_list(evidence.get("requiredOutputs"), "evidence.requiredOutputs")
    require(all(isinstance(item, str) for item in required_outputs), "evidence.requiredOutputs must contain file names")
    missing_outputs = sorted(set(EXPECTED_EVIDENCE_FILES) - set(required_outputs))
    require(not missing_outputs, f"evidence.requiredOutputs missing expected files: {', '.join(missing_outputs)}")

    return {
        "metadata": metadata,
        "actions": actions,
        "provenance": provenance,
        "policy": policy,
        "evidence": evidence,
    }


def stable_run_id(manifest: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "metadata": manifest.get("metadata", {}),
            "actions": manifest.get("actions", []),
            "provenance": manifest.get("provenance", {}),
            "policy": manifest.get("policy", {}),
            "evidence": manifest.get("evidence", {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"par-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
