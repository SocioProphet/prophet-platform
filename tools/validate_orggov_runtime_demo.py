#!/usr/bin/env python3
"""Validate OrgGov v0.2 runtime-demo contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.schema.json"
EXAMPLE = ROOT / "contracts/orggov/orggov-runtime-demo.v0.2.example.json"


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def validate_invariants(record: dict[str, Any]) -> None:
    if record.get("schemaVersion") != "orggov.runtime-demo.v0.2":
        fail("schemaVersion must be orggov.runtime-demo.v0.2")
    if record.get("recordType") != "OrgGovRuntimeDemo":
        fail("recordType must be OrgGovRuntimeDemo")
    owner_repos = set(record.get("ownerRepos", []))
    if len(owner_repos) != record.get("validation", {}).get("observedOwnerRepoCount"):
        fail("observedOwnerRepoCount must equal unique ownerRepos count")
    if record.get("validation", {}).get("requiredOwnerRepoCount") != 11 or len(owner_repos) != 11:
        fail("OrgGov v0.2 requires all 11 owner repos")

    required_states = set(record.get("validation", {}).get("requiredPolicyStates", []))
    observed_states = {item.get("state") for item in record.get("policyStateCoverage", [])}
    canonical_states = {"allow", "allow_with_constraints", "deny", "escalate", "blocked_expected", "revoke"}
    if required_states != canonical_states:
        fail("requiredPolicyStates must match the six canonical states")
    if required_states - observed_states:
        fail("policyStateCoverage missing states: " + ", ".join(sorted(required_states - observed_states)))
    if not all(item.get("covered") is True for item in record.get("policyStateCoverage", [])):
        fail("all policyStateCoverage entries must be covered")

    required_stages = {
        "stage:work-order",
        "stage:control-room",
        "stage:authority",
        "stage:policy",
        "stage:execution",
        "stage:model-tool-receipt",
        "stage:state-integrity",
        "stage:search-trace",
        "stage:scorecard",
        "stage:topology",
    }
    observed_stages = {stage.get("stageId") for stage in record.get("demoStages", [])}
    if required_stages - observed_stages:
        fail("demoStages missing required stages: " + ", ".join(sorted(required_stages - observed_stages)))
    for stage in record.get("demoStages", []):
        if stage.get("ownerRepo") not in owner_repos:
            fail(f"stage {stage.get('stageId')} owner repo is not declared")
        if not stage.get("inputRefs") or not stage.get("outputRefs"):
            fail(f"stage {stage.get('stageId')} must have inputRefs and outputRefs")

    boundary = record.get("evidenceBoundary", {})
    if not boundary.get("fixtureEvidenceRefs"):
        fail("fixtureEvidenceRefs must be non-empty")
    if record.get("demoStatus") == "fixture_backed" and boundary.get("runtimeEvidenceRefs"):
        fail("fixture_backed demos must not claim runtimeEvidenceRefs")
    forbidden = {str(item).lower() for item in boundary.get("forbiddenEvidence", [])}
    for required in ("secrets", "credentials", "private local state"):
        if required not in forbidden:
            fail(f"forbiddenEvidence must include {required!r}")
    if not record.get("proofObligations"):
        fail("proofObligations must be non-empty")
    if not record.get("runtimePromotionCriteria"):
        fail("runtimePromotionCriteria must be non-empty")
    if record.get("provenance", {}).get("nonSecret") is not True:
        fail("provenance.nonSecret must be true")


def main() -> int:
    try:
        schema = load_json(SCHEMA)
        example = load_json(EXAMPLE)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail("schema must declare JSON Schema draft 2020-12")
        validate_invariants(example)
    except ValidationError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("ok: contracts/orggov/orggov-runtime-demo.v0.2.example.json validates")
    print("OK: OrgGov v0.2 runtime demo validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
