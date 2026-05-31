#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts" / "agentplane" / "prometheus-sr-gate-policy-provenance.manifest.json"
FIXTURE = ROOT / "tests" / "fixtures" / "prometheus" / "agentplane-sr-gate-policy.valid.json"
WORKFLOW = ROOT / ".github" / "workflows" / "prometheus-jsonld.yml"
EMITTER = ROOT / "tools" / "emit_prometheus_gate_evaluation.py"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"expected object: {path}")
    return data


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != "prophet-platform.agentplane-sr-gate-policy-provenance.v0.1":
        fail("manifest schemaVersion mismatch")
    if manifest.get("recordType") != "AgentPlaneSRGatePolicyProvenanceManifest":
        fail("manifest recordType mismatch")
    if manifest.get("authorityRepo") != "SocioProphet/agentplane":
        fail("authorityRepo mismatch")
    if manifest.get("authorityCommit") != "e508e1e1565e9ce316339448c50f7325cc36676b":
        fail("authorityCommit mismatch")
    if manifest.get("authorityPath") != "schemas/symbolic-regression/sr-gate-policy.schema.json":
        fail("authorityPath mismatch")
    blob = manifest.get("authorityBlobSha")
    if not isinstance(blob, str) or len(blob) != 40:
        fail("authorityBlobSha must be git blob SHA")
    if manifest.get("authoritySchemaId") != "https://socioprophet.io/schemas/agentplane/sr-gate-policy/v0.1.0":
        fail("authoritySchemaId mismatch")
    boundary = manifest.get("authorityBoundary")
    if not isinstance(boundary, dict):
        fail("authorityBoundary must be object")
    required_false = [
        "prophetPlatformSchemaAuthority",
        "controlAuthorityGranted",
        "assertionAdmissionGranted",
        "deploymentAuthorizationGranted",
        "memoryWritebackGranted",
    ]
    for key in required_false:
        if boundary.get(key) is not False:
            fail(f"authorityBoundary.{key} must be false")
    if boundary.get("agentPlaneSchemaAuthority") is not True:
        fail("AgentPlane schema authority must be true")
    if boundary.get("prophetPlatformRuntimeConsumer") is not True:
        fail("Prophet Platform runtime consumer must be true")


def validate_fixture(manifest: dict[str, Any], fixture: dict[str, Any]) -> None:
    fields = manifest.get("requiredFields")
    if not isinstance(fields, list) or not fields:
        fail("manifest requiredFields missing")
    missing = sorted(set(fields) - set(fixture))
    if missing:
        fail(f"fixture missing AgentPlane SRGatePolicy fields: {missing}")
    if fixture.get("schemaVersion") != "0.1.0":
        fail("fixture schemaVersion mismatch")
    if fixture.get("requiredUnitsStatus") != "consistent":
        fail("fixture must require consistent units")
    if fixture.get("requireReplayVerified") is not True:
        fail("fixture must require replay verification")
    if fixture.get("allowControlAuthority") is not False:
        fail("fixture must forbid control authority")
    if fixture.get("promotionEligibility") != "review_required":
        fail("fixture must require review, not automatic admission")


def validate_consumer_paths(manifest: dict[str, Any]) -> None:
    if manifest.get("consumerFixture") != "tests/fixtures/prometheus/agentplane-sr-gate-policy.valid.json":
        fail("consumerFixture mismatch")
    if manifest.get("consumerWorkflow") != ".github/workflows/prometheus-jsonld.yml":
        fail("consumerWorkflow mismatch")
    if manifest.get("consumerEmitter") != "tools/emit_prometheus_gate_evaluation.py":
        fail("consumerEmitter mismatch")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    emitter = EMITTER.read_text(encoding="utf-8")
    for token in ("agentplane-sr-gate-policy.valid.json", "--gate-policy"):
        if token not in workflow:
            fail(f"workflow missing token: {token}")
    for token in ("--gate-policy", "allowControlAuthority", "requireReplayVerified", "promotionEligibility"):
        if token not in emitter:
            fail(f"emitter missing token: {token}")


def main() -> int:
    manifest = load_json(MANIFEST)
    fixture = load_json(FIXTURE)
    validate_manifest(manifest)
    validate_fixture(manifest, fixture)
    validate_consumer_paths(manifest)
    print(json.dumps({"valid": True, "manifest": str(MANIFEST)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
