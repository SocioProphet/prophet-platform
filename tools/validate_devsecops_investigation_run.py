#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-investigation-run-v0.1.schema.json"
VALID_FIXTURES = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-investigation-run.post-merge.valid.json",
]


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"schema:{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    boundary = data.get("authority_boundary", {})
    evidence = data.get("evidence_collection", [])
    evidence_refs = {item.get("evidence_ref") for item in evidence if isinstance(item, dict)}
    collected_refs = {item.get("evidence_ref") for item in evidence if isinstance(item, dict) and item.get("collection_status") == "collected"}
    topology_sources = {
        item.get("source_ref")
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_type") == "topology_snapshot"
    }
    topology_context = data.get("topology_context", {})
    blast_context = data.get("blast_radius_context", {})
    projection = data.get("workroom_projection", {})
    projected_sources = projection.get("source_refs", {}) if isinstance(projection, dict) else {}
    projected_evidence = set(projection.get("evidence_refs", [])) if isinstance(projection, dict) else set()

    if boundary.get("workroom_authority") != "prophet_platform":
        problems.append("workroom authority must remain prophet_platform")
    if boundary.get("execution_authority") == "agentplane" and data.get("status") == "ready_for_rca":
        problems.append("agentplane execution authority requires explicit execution receipt before ready_for_rca")
    if data.get("lane") != "post_merge_incident":
        problems.append("InvestigationRun lane must be post_merge_incident")
    if data.get("investigation_run_ref") != projected_sources.get("investigation_run_ref"):
        problems.append("projection investigation_run_ref must match InvestigationRun investigation_run_ref")
    if data.get("incident_ref") != projected_sources.get("incident_ref"):
        problems.append("projection incident_ref must match InvestigationRun incident_ref")

    topology_ref = topology_context.get("topology_ref")
    topology_evidence_ref = topology_context.get("evidence_ref")
    if not topology_ref or topology_ref not in topology_sources:
        problems.append("topology_context.topology_ref must be backed by topology_snapshot source_ref")
    if topology_evidence_ref not in evidence_refs:
        problems.append("topology_context.evidence_ref must reference evidence")
    if topology_evidence_ref not in collected_refs:
        problems.append("topology_context.evidence_ref must reference collected evidence")

    if blast_context.get("topology_ref") != topology_ref:
        problems.append("blast_radius_context.topology_ref must match topology_context.topology_ref")
    if blast_context.get("blast_radius_ref") != projected_sources.get("blast_radius_ref"):
        problems.append("projection blast_radius_ref must match blast_radius_context.blast_radius_ref")
    if projected_sources.get("topology_ref") != topology_ref:
        problems.append("projection topology_ref must match topology_context.topology_ref")

    missing_projected_evidence = sorted(projected_evidence - evidence_refs)
    if missing_projected_evidence:
        problems.append(f"projection evidence_refs missing from evidence_collection: {missing_projected_evidence}")
    if data.get("status") == "ready_for_rca" and not collected_refs:
        problems.append("ready_for_rca requires at least one collected evidence item")

    return problems


def main() -> int:
    schema = load(SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}
    for path in VALID_FIXTURES:
        data = load(path)
        schema_errors = schema_problems(schema, data)
        semantic_errors = semantic_problems(data)
        failed = failed or bool(schema_errors or semantic_errors)
        results[str(path.relative_to(ROOT))] = {
            "expected": "valid",
            "schema": schema_errors,
            "semantic": semantic_errors,
        }
    report = {
        "validator": "prophet-platform.devsecops-investigation-run.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Validator checks InvestigationRun contract and fixture semantics.",
            "Validator does not execute incident investigation commands.",
            "Validator does not authorize production remediation.",
            "Validator does not confirm root cause."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops investigation run fixtures")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
