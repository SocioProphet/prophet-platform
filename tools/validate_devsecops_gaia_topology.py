#!/usr/bin/env python3
"""
Validator for DevSecOps GAIA topology snapshot ref and blast-radius estimate contracts.

Topology snapshot rules:
  1. snapshot_digest must be non-empty (enforced by schema).

Blast-radius estimate rules:
  1. customer_impact_class=high requires at least one evidence_ref.
  2. confidence=none means no causal estimate — affected_services should be empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-topology-snapshot-ref-v0.1.schema.json"
BLAST_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-blast-radius-estimate-v0.1.schema.json"

TOPOLOGY_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-topology-snapshot-ref.post-merge.valid.json",
]
TOPOLOGY_INVALID: dict[Path, list[str]] = {}

BLAST_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-blast-radius-estimate.topology-supported.valid.json",
]
BLAST_INVALID: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-blast-radius-estimate.high-impact-no-evidence.invalid.json": [
        "customer_impact_class=high requires at least one evidence_ref",
    ],
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    v = jsonschema.Draft7Validator(schema)
    return [e.message for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))]


def blast_semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    rid = data.get("blast_radius_ref", "<unknown>")
    customer_impact = data.get("customer_impact_class", "")
    confidence = data.get("confidence", "")
    evidence_refs = data.get("evidence_refs") or []

    if customer_impact == "high" and not evidence_refs:
        problems.append(
            f"{rid}: customer_impact_class=high requires at least one evidence_ref"
        )

    if confidence == "none" and data.get("affected_services"):
        problems.append(
            f"{rid}: confidence=none means no causal estimate; affected_services should be empty"
        )

    return problems


def expect(path: Path, problems: list[str], expected_substrings: list[str]) -> list[str]:
    failures: list[str] = []
    if not problems:
        failures.append(f"{path}: expected invalid fixture to fail, but it passed")
    for expected in expected_substrings:
        if not any(expected in p for p in problems):
            failures.append(f"{path}: expected problem containing {expected!r}")
    return failures


def main() -> int:
    topo_schema = load(TOPOLOGY_SCHEMA)
    blast_schema = load(BLAST_SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    for path in TOPOLOGY_VALID:
        data = load(path)
        s_errs = schema_problems(topo_schema, data)
        failed = failed or bool(s_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs}

    for path, expected in TOPOLOGY_INVALID.items():
        data = load(path)
        s_errs = schema_problems(topo_schema, data)
        failures = expect(path.relative_to(ROOT), s_errs, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs,
        }

    for path in BLAST_VALID:
        data = load(path)
        s_errs = schema_problems(blast_schema, data)
        sem_errs = blast_semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs, "semantic": sem_errs}

    for path, expected in BLAST_INVALID.items():
        data = load(path)
        s_errs = schema_problems(blast_schema, data)
        sem_errs = blast_semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs, "semantic": sem_errs,
        }

    report = {
        "validator": "prophet-platform.devsecops-gaia-topology.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "GAIA is the topology and blast-radius authority.",
            "Validator checks snapshot ref and blast-radius estimate contract structure only.",
            "Validator does not execute topology probes or query live GAIA graphs.",
            "Validator does not prove incident root cause or authorize remediation.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops gaia topology")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
