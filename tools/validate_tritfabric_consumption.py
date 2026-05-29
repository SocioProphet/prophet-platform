#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "integrations" / "tritfabric-consumption.v0.json"
REQUIRED_SURFACES = {
    "community-learning-intake",
    "network-atlas-framework-catalog",
    "model-card-promotion-evidence",
    "serve-readiness",
}
REQUIRED_NON_CLAIMS = {
    "runtime-implementation",
    "event-ingestion",
    "workflow-execution",
    "adapter-validation",
    "serve-deployment",
}


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def validate_contract(doc: dict) -> None:
    if doc.get("schema_version") != "prophet-platform.integration-consumption/v0.1":
        raise AssertionError("unexpected schema_version")
    upstreams = doc.get("upstreams", {})
    for key in ("implementation", "estate_registration", "vocabulary"):
        if not upstreams.get(key):
            raise AssertionError(f"missing upstream {key}")
    boundaries = doc.get("authority_boundaries", {})
    if boundaries.get("prophet_platform") != "consumer":
        raise AssertionError("Prophet Platform must remain consumer")
    if boundaries.get("tritfabric") != "implementation-and-contract-owner":
        raise AssertionError("TritFabric ownership boundary missing")
    surface_ids = {surface.get("id") for surface in doc.get("surfaces", [])}
    missing = REQUIRED_SURFACES - surface_ids
    if missing:
        raise AssertionError(f"missing surfaces: {sorted(missing)}")
    non_claims = set(doc.get("non_claims", []))
    missing_non_claims = REQUIRED_NON_CLAIMS - non_claims
    if missing_non_claims:
        raise AssertionError(f"missing non-claims: {sorted(missing_non_claims)}")
    community = next(surface for surface in doc["surfaces"] if surface["id"] == "community-learning-intake")
    for gate in ("consent", "license", "lineage", "rubric", "manual-review-before-promotion"):
        if gate not in community.get("required_gates", []):
            raise AssertionError(f"community surface missing gate {gate}")
    model_card = next(surface for surface in doc["surfaces"] if surface["id"] == "model-card-promotion-evidence")
    for field in ("mathType", "calcOps", "ledgerRef", "artifactRef", "tritStatus"):
        if field not in model_card.get("required_fields", []):
            raise AssertionError(f"model-card surface missing field {field}")


def main() -> int:
    validate_contract(load_contract())
    print("tritfabric consumption contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
