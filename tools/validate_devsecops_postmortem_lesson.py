#!/usr/bin/env python3
"""
Validator for DevSecOps PostmortemLesson and Academy canonization handoff contracts.

PostmortemLesson rules:
  1. canonical lesson requires at least one regression_fixture_ref.
  2. canonical lesson requires canonization_target_ref.
  3. rejected lesson must not have regression_fixture_refs.
  4. superseded lesson requires successor_lesson_ref.

Academy handoff rules:
  1. canonized status requires academy_decision_ref.
  2. rejected status requires academy_decision_ref.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
LESSON_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-postmortem-lesson-v0.1.schema.json"
HANDOFF_SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-academy-canonization-handoff-v0.1.schema.json"

LESSON_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-postmortem-lesson.accepted.valid.json",
]
LESSON_INVALID: dict[Path, list[str]] = {
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-postmortem-lesson.canonical-no-regression-fixture.invalid.json": [
        "canonical lesson requires at least one regression_fixture_ref",
    ],
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-postmortem-lesson.superseded-no-successor.invalid.json": [
        "superseded lesson requires successor_lesson_ref",
    ],
}

HANDOFF_VALID = [
    ROOT / "tests" / "fixtures" / "workroom" / "devsecops-academy-canonization-handoff.submitted.valid.json",
]
HANDOFF_INVALID: dict[Path, list[str]] = {}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_problems(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    v = jsonschema.Draft7Validator(schema)
    return [e.message for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))]


def lesson_semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    lid = data.get("lesson_id", "<unknown>")
    status = data.get("lesson_status", "")
    regression_fixture_refs = data.get("regression_fixture_refs") or []

    if status == "canonical":
        if not regression_fixture_refs:
            problems.append(f"{lid}: canonical lesson requires at least one regression_fixture_ref")
        if not data.get("canonization_target_ref"):
            problems.append(f"{lid}: canonical lesson requires canonization_target_ref")

    if status == "rejected" and regression_fixture_refs:
        problems.append(f"{lid}: rejected lesson must not have regression_fixture_refs")

    if status == "superseded" and not data.get("successor_lesson_ref"):
        problems.append(f"{lid}: superseded lesson requires successor_lesson_ref")

    return problems


def handoff_semantic_problems(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    hid = data.get("handoff_id", "<unknown>")
    status = data.get("status", "")

    if status in ("canonized", "rejected") and not data.get("academy_decision_ref"):
        problems.append(f"{hid}: {status} handoff requires academy_decision_ref")

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
    lesson_schema = load(LESSON_SCHEMA)
    handoff_schema = load(HANDOFF_SCHEMA)
    failed = False
    results: dict[str, dict[str, Any]] = {}

    for path in LESSON_VALID:
        data = load(path)
        s_errs = schema_problems(lesson_schema, data)
        sem_errs = lesson_semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs, "semantic": sem_errs}

    for path, expected in LESSON_INVALID.items():
        data = load(path)
        s_errs = schema_problems(lesson_schema, data)
        sem_errs = lesson_semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs, "semantic": sem_errs,
        }

    for path in HANDOFF_VALID:
        data = load(path)
        s_errs = schema_problems(handoff_schema, data)
        sem_errs = handoff_semantic_problems(data)
        failed = failed or bool(s_errs or sem_errs)
        results[str(path.relative_to(ROOT))] = {"expected": "valid", "schema": s_errs, "semantic": sem_errs}

    for path, expected in HANDOFF_INVALID.items():
        data = load(path)
        s_errs = schema_problems(handoff_schema, data)
        sem_errs = handoff_semantic_problems(data)
        problems = s_errs + sem_errs
        failures = expect(path.relative_to(ROOT), problems, expected)
        failed = failed or bool(failures)
        results[str(path.relative_to(ROOT))] = {
            "expected": "invalid", "expected_problem_substrings": expected,
            "expectation_failures": failures, "schema": s_errs, "semantic": sem_errs,
        }

    report = {
        "validator": "prophet-platform.devsecops-postmortem-lesson.validator.v1",
        "passed": not failed,
        "results": results,
        "non_claims": [
            "Prophet Platform emits lesson candidates; Alexandrian Academy decides canonization.",
            "Validator checks lesson contract structure and promotion invariants only.",
            "Validator does not canonize lessons, approve remediation, or authorize production changes.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not failed else "FAIL") + ": devsecops postmortem lesson")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
