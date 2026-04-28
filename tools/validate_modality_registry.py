#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "contracts" / "modality" / "functional-service-registry.v1.example.json"
REQUIRED_SURFACES = {
    "language",
    "sourceos-carry",
    "speech",
    "ocr",
    "image",
    "video",
    "translation",
    "embedding",
    "routing",
    "guardrail",
    "agent-registry",
}


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not REGISTRY.exists():
        return fail(f"missing registry: {REGISTRY}")
    data = json.loads(REGISTRY.read_text())
    if data.get("apiVersion") != "modality.socioprophet.dev/v1":
        return fail("apiVersion must be modality.socioprophet.dev/v1")
    if data.get("kind") != "FunctionalServiceRegistry":
        return fail("kind must be FunctionalServiceRegistry")
    services = data.get("spec", {}).get("services", [])
    if not services:
        return fail("registry must contain services")

    surfaces = set()
    ids = set()
    for idx, service in enumerate(services):
        prefix = f"services[{idx}]"
        service_id = service.get("serviceId")
        if not service_id or not str(service_id).startswith("service://"):
            return fail(f"{prefix}.serviceId must be a service:// ref")
        if service_id in ids:
            return fail(f"duplicate serviceId: {service_id}")
        ids.add(service_id)

        surface = service.get("surface")
        if not surface:
            return fail(f"{prefix}.surface is required")
        surfaces.add(surface)
        if service.get("status") not in {"bootstrap", "experimental", "stable", "deprecated"}:
            return fail(f"{prefix}.status is invalid")
        if not service.get("sourceRepos"):
            return fail(f"{prefix}.sourceRepos is required")
        if not service.get("evidenceRequirements"):
            return fail(f"{prefix}.evidenceRequirements is required")
        promotion = service.get("promotion", {})
        if not promotion.get("state") or not promotion.get("rollbackRef"):
            return fail(f"{prefix}.promotion.state and rollbackRef are required")
        carry = service.get("sourceosCarryPolicy", {})
        if carry.get("role") != "carry-only":
            return fail(f"{prefix}.sourceosCarryPolicy.role must be carry-only")
        if carry.get("mayReplaceServiceArtifact") is not False:
            return fail(f"{prefix}.sourceosCarryPolicy.mayReplaceServiceArtifact must be false")
        if carry.get("mayPromoteModel") is not False:
            return fail(f"{prefix}.sourceosCarryPolicy.mayPromoteModel must be false")

    missing = sorted(REQUIRED_SURFACES - surfaces)
    if missing:
        return fail(f"missing required surfaces: {missing}")
    print(f"OK: validated {len(services)} functional service records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
