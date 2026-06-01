#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "integrations" / "tritfabric-ui-labels.v0.json"
EXPECTED_SURFACES = {
    "community-learning-intake",
    "network-atlas-framework-catalog",
    "model-card-promotion-evidence",
    "serve-readiness",
}
FORBIDDEN_BADGES = {
    "training-enabled",
    "auto-promotion",
    "economic-credit",
    "validated-adapter",
    "production-supported",
    "promotion-executor",
    "transport-exception-only",
    "production-ready",
    "autoscaler-active",
    "serve-deployed",
}


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def validate_contract(doc: dict) -> None:
    if doc.get("schema_version") != "prophet-platform.tritfabric-ui-labels/v0.1":
        raise AssertionError("unexpected schema_version")
    if doc.get("contract_id") != "tritfabric-ui-labels-v0":
        raise AssertionError("unexpected contract_id")
    labels = doc.get("labels")
    if not isinstance(labels, list):
        raise AssertionError("labels must be a list")
    by_surface = {label.get("surface_id"): label for label in labels}
    missing = EXPECTED_SURFACES - set(by_surface)
    extra = set(by_surface) - EXPECTED_SURFACES
    if missing or extra:
        raise AssertionError(f"surface mismatch missing={sorted(missing)} extra={sorted(extra)}")
    for surface_id, label in by_surface.items():
        for field in ("display_label", "status_label", "must_show", "forbidden_badges"):
            if field not in label:
                raise AssertionError(f"{surface_id} missing {field}")
        if not label["display_label"] or not label["status_label"]:
            raise AssertionError(f"{surface_id} labels must be non-empty")
        if not isinstance(label["must_show"], list) or not label["must_show"]:
            raise AssertionError(f"{surface_id} must_show must be non-empty")
        forbidden = set(label.get("forbidden_badges", []))
        if not forbidden:
            raise AssertionError(f"{surface_id} must declare forbidden_badges")
        if not forbidden.issubset(FORBIDDEN_BADGES):
            raise AssertionError(f"{surface_id} has unknown forbidden badges: {sorted(forbidden - FORBIDDEN_BADGES)}")
    community = by_surface["community-learning-intake"]
    for gate in ("consent", "license", "lineage", "rubric", "manual-review-before-promotion"):
        if gate not in community["must_show"]:
            raise AssertionError(f"community-learning-intake must show {gate}")
    serve = by_surface["serve-readiness"]
    if "production-ready" not in serve["forbidden_badges"] or "autoscaler-active" not in serve["forbidden_badges"]:
        raise AssertionError("serve-readiness must forbid production-ready and autoscaler-active badges")
    boundary = doc.get("claim_boundary", "")
    for phrase in ("does not implement UI", "runtime behavior", "production readiness"):
        if phrase not in boundary:
            raise AssertionError(f"claim_boundary missing phrase: {phrase}")


def main() -> int:
    validate_contract(load_contract())
    print("tritfabric UI labels: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
