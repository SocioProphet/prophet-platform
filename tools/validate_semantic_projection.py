#!/usr/bin/env python3
"""Validate Semantic Projection Kernel v0.1 contracts and fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "semantic-projection"
SCHEMAS = [
    "projection-request.v0.1.schema.json",
    "projection-result.v0.1.schema.json",
    "claim-record.v0.1.schema.json",
    "contradiction-record.v0.1.schema.json",
    "projection-audit-record.v0.1.schema.json",
]
REQUIRED_BY_TYPE = {
    "ProjectionRequest": ["schemaVersion", "recordType", "requestId", "userId", "intent", "timeHorizon", "policyContext", "memoryScope", "contradictionPolicy", "actionContext", "provenance"],
    "ProjectionResult": ["schemaVersion", "recordType", "requestId", "projectionId", "createdAt", "semanticStateSnapshotId", "projectedSurfaceId", "visibleClaims", "visibleEntities", "visibleRelationships", "visibleEvidence", "contradictions", "redactions", "contradictionHandling", "explanation", "actionEligibility", "provenance"],
    "ClaimRecord": ["schemaVersion", "recordType", "claimId", "claimType", "subjectIds", "predicate", "objectIds", "statement", "provenance", "temporal", "confidence", "promotion", "contradictions", "policy"],
    "ContradictionRecord": ["schemaVersion", "recordType", "contradictionId", "contradictionType", "claimIds", "status", "explanation", "detectedAt", "policyHandling"],
    "ProjectionAuditRecord": ["schemaVersion", "recordType", "projectionId", "requestId", "userId", "groupoidId", "semanticStateSnapshotId", "policyBundleIds", "modelVersions", "deterministicReplayKey", "inputHash", "outputHash", "createdAt"],
}

class ValidationError(Exception):
    pass

def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))

def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{rel(path)}: expected JSON object")
    return value

def require(record: dict[str, Any], keys: list[str], path: str) -> None:
    for key in keys:
        if key not in record:
            raise ValidationError(f"{path}: missing required key {key!r}")

def require_nonempty(value: Any, path: str) -> None:
    if isinstance(value, str) and value.strip():
        return
    if isinstance(value, list) and value:
        return
    raise ValidationError(f"{path}: must be non-empty")

def validate_schemas() -> None:
    for name in SCHEMAS:
        schema = load_json(CONTRACT_DIR / name)
        require(schema, ["$schema", "$id", "title", "type", "required", "properties"], rel(CONTRACT_DIR / name))
        if schema.get("type") != "object":
            raise ValidationError(f"{name}: schema type must be object")

def validate_request(record: dict[str, Any]) -> None:
    policy = record["policyContext"]
    require(policy, ["authorizationProfileId", "trustPolicyId", "redactionPolicyId", "explanationLevel"], "policyContext")
    require_nonempty(policy["authorizationProfileId"], "policyContext.authorizationProfileId")
    require_nonempty(policy["trustPolicyId"], "policyContext.trustPolicyId")
    require_nonempty(policy["redactionPolicyId"], "policyContext.redactionPolicyId")
    action = record["actionContext"]
    require(action, ["actionRequested", "actionType"], "actionContext")
    if action["actionRequested"] and not action["actionType"]:
        raise ValidationError("actionContext.actionType required when actionRequested=true")

def validate_claim(record: dict[str, Any]) -> None:
    provenance = record["provenance"]
    promotion = record["promotion"]
    policy = record["policy"]
    require(provenance, ["sourceArtifactIds", "derivationPath", "producerType", "producerId", "transformationIds"], "provenance")
    require(promotion, ["status", "validatorIds", "reviewIds"], "promotion")
    require(policy, ["reuseScope", "actionEligible"], "policy")
    if promotion["status"] == "promoted":
        require_nonempty(provenance["sourceArtifactIds"], "provenance.sourceArtifactIds")
        if not promotion["validatorIds"] and not promotion["reviewIds"]:
            raise ValidationError("promoted claims require validatorIds or reviewIds")
    if policy["actionEligible"] and promotion["status"] != "promoted":
        raise ValidationError("only promoted claims may be action eligible")

def validate_contradiction(record: dict[str, Any]) -> None:
    if len(record["claimIds"]) < 2:
        raise ValidationError("contradiction records require at least two claimIds")
    handling = record["policyHandling"]
    require(handling, ["mode", "rationale"], "policyHandling")

def validate_result(record: dict[str, Any]) -> None:
    explanation = record["explanation"]
    provenance = record["provenance"]
    action = record["actionEligibility"]
    handling = record["contradictionHandling"]
    redactions = record["redactions"]
    require(explanation, ["summary", "policyBasis", "provenanceBasis"], "explanation")
    require(provenance, ["sourceProjectionRequestId", "policyBundleIds", "claimRecordRefs"], "provenance")
    require(action, ["permitted", "permittedActions", "blockingReasons"], "actionEligibility")
    require(handling, ["knownContradictionCount", "mode"], "contradictionHandling")
    require(redactions, ["count", "disclosureMode", "rationale"], "redactions")
    require_nonempty(explanation["policyBasis"], "explanation.policyBasis")
    require_nonempty(explanation["provenanceBasis"], "explanation.provenanceBasis")
    require_nonempty(provenance["policyBundleIds"], "provenance.policyBundleIds")
    if action["permitted"] and not action["permittedActions"]:
        raise ValidationError("permitted projection results require permittedActions")
    if action["permitted"] and action["blockingReasons"]:
        raise ValidationError("permitted projection results cannot carry blockingReasons")
    if handling["knownContradictionCount"] > 0:
        if handling["mode"] == "none":
            raise ValidationError("known contradictions cannot use handling mode none")
        if handling["mode"] == "exposed" and not record["contradictions"]:
            raise ValidationError("exposed contradictions must be listed")
        if handling["mode"] == "policy_suppressed" and redactions["count"] <= 0:
            raise ValidationError("policy-suppressed contradictions require redaction disclosure")

def validate_audit(record: dict[str, Any]) -> None:
    require_nonempty(record["policyBundleIds"], "policyBundleIds")
    require_nonempty(record["modelVersions"], "modelVersions")
    if not record["inputHash"].startswith("sha256:"):
        raise ValidationError("inputHash must start with sha256:")
    if not record["outputHash"].startswith("sha256:"):
        raise ValidationError("outputHash must start with sha256:")
    require_nonempty(record["deterministicReplayKey"], "deterministicReplayKey")

VALIDATORS = {
    "ProjectionRequest": validate_request,
    "ProjectionResult": validate_result,
    "ClaimRecord": validate_claim,
    "ContradictionRecord": validate_contradiction,
    "ProjectionAuditRecord": validate_audit,
}

def validate_record(path: Path) -> None:
    record = load_json(path)
    record_type = record.get("recordType")
    if record_type not in REQUIRED_BY_TYPE:
        raise ValidationError(f"{rel(path)}: unknown recordType {record_type!r}")
    require(record, REQUIRED_BY_TYPE[record_type], rel(path))
    VALIDATORS[record_type](record)

def validate_valid_fixtures() -> int:
    count = 0
    for path in sorted(CONTRACT_DIR.glob("*.example.json")):
        validate_record(path)
        print(f"ok: {rel(path)}")
        count += 1
    if count < 5:
        raise ValidationError("expected at least five valid examples")
    return count

def validate_invalid_fixtures() -> int:
    count = 0
    for path in sorted((CONTRACT_DIR / "invalid").glob("*.invalid.json")):
        try:
            validate_record(path)
        except ValidationError as exc:
            print(f"ok: rejected {rel(path)} ({exc})")
            count += 1
            continue
        raise ValidationError(f"{rel(path)} unexpectedly passed validation")
    if count < 5:
        raise ValidationError("expected at least five invalid fixtures")
    return count

def main() -> int:
    try:
        validate_schemas()
        valid_count = validate_valid_fixtures()
        invalid_count = validate_invalid_fixtures()
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: Semantic Projection validation passed ({valid_count} valid, {invalid_count} invalid rejected)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
