#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "workroom" / "devsecops-workroom-guardrail-decision-binding-v0.1.schema.json"
BINDING = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.guardrail-decision-binding.valid.json"
WORKROOM = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json"
GUARDRAIL_DIR = ROOT / "fixtures" / "external" / "guardrail-fabric" / "devsecops-workroom"
GUARDRAIL_FIXTURES = [
    GUARDRAIL_DIR / "poisoned-evidence.denied.valid.json",
    GUARDRAIL_DIR / "unsafe-mutation-without-grant.denied.valid.json",
    GUARDRAIL_DIR / "credential-sensitive.escalated.valid.json",
    GUARDRAIL_DIR / "safe-read-only-probe.allowed.valid.json",
]


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def schema_errors(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"schema:{path}: {error.message}")
    return errors


def map_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in items if isinstance(item, dict) and item.get(key)}


def semantic_errors(binding: dict[str, Any], workroom: dict[str, Any], guardrails: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    grants_by_ref = map_by(workroom.get("action_grants", []), "grant_id")
    plans_by_ref = map_by(workroom.get("remediation_plans", []), "plan_id")
    guardrails_by_ref = map_by(guardrails, "fixture_id")

    if binding.get("workroom_ref") != workroom.get("workroom_id"):
        errors.append("binding workroom_ref must equal Workroom workroom_id")

    for ref in binding.get("guardrail_fixture_refs", []):
        if ref not in guardrails_by_ref:
            errors.append(f"binding references missing Guardrail fixture {ref}")

    for action_binding in binding.get("action_grant_bindings", []):
        grant_ref = action_binding.get("grant_ref")
        fixture_ref = action_binding.get("guardrail_fixture_ref")
        grant = grants_by_ref.get(grant_ref)
        fixture = guardrails_by_ref.get(fixture_ref)
        if not grant:
            errors.append(f"action binding references missing Workroom grant {grant_ref}")
            continue
        if not fixture:
            errors.append(f"action binding references missing Guardrail fixture {fixture_ref}")
            continue
        if action_binding.get("action_class") != grant.get("action_class"):
            errors.append(f"{grant_ref}: action_class must match Workroom grant")
        if action_binding.get("workroom_grant_status") != grant.get("status"):
            errors.append(f"{grant_ref}: workroom_grant_status must match Workroom grant status")
        if action_binding.get("guardrail_expected_decision") != fixture.get("expected_decision"):
            errors.append(f"{grant_ref}: guardrail_expected_decision must match fixture expected_decision")

        if grant.get("action_class") == "read_only":
            if action_binding.get("binding_status") != "aligned":
                errors.append(f"{grant_ref}: read_only binding must be aligned")
            if fixture.get("fixture_class") != "safe_read_only_probe":
                errors.append(f"{grant_ref}: read_only binding must use safe_read_only_probe fixture")
        if grant.get("action_class") == "production_change":
            if grant.get("status") != "requires_human_approval":
                errors.append(f"{grant_ref}: production_change grant must require human approval")
            if action_binding.get("binding_status") != "requires_review":
                errors.append(f"{grant_ref}: production_change binding must require review")

    for remediation_binding in binding.get("remediation_bindings", []):
        plan_ref = remediation_binding.get("plan_ref")
        plan = plans_by_ref.get(plan_ref)
        fixture = guardrails_by_ref.get(remediation_binding.get("guardrail_fixture_ref"))
        if not plan:
            errors.append(f"remediation binding references missing Workroom plan {plan_ref}")
            continue
        if not fixture:
            errors.append(f"remediation binding references missing Guardrail fixture {remediation_binding.get('guardrail_fixture_ref')}")
            continue
        if remediation_binding.get("risk_class") != plan.get("risk_class"):
            errors.append(f"{plan_ref}: risk_class must match Workroom plan")
        if remediation_binding.get("plan_status") != plan.get("plan_status"):
            errors.append(f"{plan_ref}: plan_status must match Workroom plan")
        if remediation_binding.get("required_action_grant_refs") != plan.get("required_action_grant_refs"):
            errors.append(f"{plan_ref}: required_action_grant_refs must match Workroom plan")
        if remediation_binding.get("guardrail_expected_decision") != fixture.get("expected_decision"):
            errors.append(f"{plan_ref}: guardrail_expected_decision must match fixture expected_decision")
        if plan.get("risk_class") in {"high", "critical"} and remediation_binding.get("binding_status") != "requires_review":
            errors.append(f"{plan_ref}: high/critical remediation binding must require review")
        if plan.get("plan_status") == "executed":
            errors.append(f"{plan_ref}: binding fixture must not execute remediation")

    non_claims = "\n".join(str(item) for item in binding.get("non_claims", [])).lower()
    for required in ("does not execute", "does not authorize remediation", "does not certify signadot"):
        if not all(word in non_claims for word in required.split()):
            errors.append(f"binding non_claims must preserve {required!r} posture")

    return errors


def main() -> int:
    schema = load(SCHEMA)
    binding = load(BINDING)
    workroom = load(WORKROOM)
    guardrails = [load(path) for path in GUARDRAIL_FIXTURES]
    errors = schema_errors(schema, binding) + semantic_errors(binding, workroom, guardrails)
    report = {
        "validator": "prophet-platform.workroom-guardrail-decision-binding.validator.v1",
        "passed": not errors,
        "errors": errors,
        "inputs": {
            "binding": str(BINDING.relative_to(ROOT)),
            "workroom": str(WORKROOM.relative_to(ROOT)),
            "guardrails": [str(path.relative_to(ROOT)) for path in GUARDRAIL_FIXTURES],
        },
        "non_claims": [
            "Validator checks Workroom-to-Guardrail binding posture only.",
            "Validator does not execute infrastructure.",
            "Validator does not inspect production systems.",
            "Validator does not authorize remediation.",
            "Validator does not certify Signadot feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not errors else "FAIL") + ": Workroom Guardrail decision binding")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
