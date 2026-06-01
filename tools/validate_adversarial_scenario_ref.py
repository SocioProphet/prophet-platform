#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "security" / "adversarial-scenario-ref.schema.json"
EXAMPLE_PATH = ROOT / "contracts" / "security" / "adversarial-scenario-ref.example.json"

REQUIRED_NON_CLAIMS = {
    "does_not_execute_attack_procedure",
    "does_not_authorize_engagement",
    "does_not_claim_causal_attribution",
    "does_not_promote_memory_writeback",
    "does_not_establish_production_observation",
}


def fail(message: str) -> int:
    print(f"ERR: {message}", file=sys.stderr)
    return 1


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must be a JSON object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_object(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{name} must be an object")
    return value


def require_false(obj: dict[str, Any], key: str, context: str) -> None:
    require(obj.get(key) is False, f"{context}.{key} must be false")


def validate_schema(schema: dict[str, Any]) -> None:
    require(schema.get("title") == "Platform Adversarial Scenario Reference", "schema title mismatch")
    props = require_object(schema.get("properties"), "schema.properties")
    require(props.get("schemaVersion", {}).get("const") == "0.1.0", "schemaVersion const missing")
    source = require_object(props.get("source"), "schema.properties.source")
    source_props = require_object(source.get("properties"), "schema.properties.source.properties")
    require(source_props.get("scenarioRepo", {}).get("const") == "SocioProphet/SCOPE-D", "scenarioRepo const must point to SCOPE-D")


def validate_example(example: dict[str, Any]) -> None:
    require(example.get("schemaVersion") == "0.1.0", "example schemaVersion mismatch")
    require(str(example.get("scenarioRef", "")).startswith("adversarial-scenario:"), "scenarioRef must use adversarial-scenario: prefix")

    source = require_object(example.get("source"), "source")
    require(source.get("scenarioRepo") == "SocioProphet/SCOPE-D", "source.scenarioRepo must be SocioProphet/SCOPE-D")
    for key in ("scenarioPrRef", "schemaRef", "ontologyRef"):
        require(isinstance(source.get(key), str) and source[key], f"source.{key} must be non-empty string")

    require(example.get("bindingMode") == "reference_only", "bindingMode must be reference_only in the example")

    platform_use = require_object(example.get("platformUse"), "platformUse")
    for key in ("runtimeExecution", "reportExport", "memoryWriteback", "claimPromotion"):
        require_false(platform_use, key, "platformUse")
    require(platform_use.get("apiSurface") == "contract_reference", "platformUse.apiSurface must be contract_reference")
    require(platform_use.get("uiSurface") == "none", "platformUse.uiSurface must be none")

    safety = require_object(example.get("safetyBoundary"), "safetyBoundary")
    require(safety.get("nonProductionOnly") is True, "safetyBoundary.nonProductionOnly must be true")
    require(safety.get("syntheticOrRedacted") is True, "safetyBoundary.syntheticOrRedacted must be true")
    for key in ("liveTargetAccess", "credentialAccess", "payloadDelivery", "stateMutation", "destructiveBehavior", "externalDelivery"):
        require_false(safety, key, "safetyBoundary")

    authority = require_object(example.get("authority"), "authority")
    for key in ("runtimeAuthority", "procedureExecutionAuthority", "engagementAuthorizationAuthority", "activationAllowed"):
        require_false(authority, key, "authority")

    for key in ("evidenceRefs", "runtimeDecisionReceiptRefs", "policyRefs", "semanticNonClaims"):
        value = example.get(key)
        require(isinstance(value, list) and value, f"{key} must be a non-empty list")

    receipt_refs = example.get("runtimeDecisionReceiptRefs") or []
    require(all(isinstance(ref, str) and ref.startswith("wargames-runtime-receipt:") for ref in receipt_refs), "runtimeDecisionReceiptRefs must use wargames-runtime-receipt: prefix")

    non_claims = set(example.get("semanticNonClaims") or [])
    missing = sorted(REQUIRED_NON_CLAIMS - non_claims)
    require(not missing, f"semanticNonClaims missing required non-claims: {missing}")
    require(example.get("redactionState") in {"redacted", "synthetic", "withheld"}, "invalid redactionState")


def main() -> int:
    try:
        schema = load_json(SCHEMA_PATH)
        example = load_json(EXAMPLE_PATH)
        validate_schema(schema)
        validate_example(example)
    except ValueError as exc:
        return fail(str(exc))

    print("OK: validated adversarial scenario reference schema and example")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
