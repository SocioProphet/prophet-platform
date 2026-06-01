#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKROOM = ROOT / "tests" / "fixtures" / "workroom" / "devsecops-workroom.post-merge-incident.valid.json"
GUARDRAIL_FIXTURES = [
    ROOT / "fixtures" / "external" / "guardrail-fabric" / "devsecops-workroom" / "poisoned-evidence.denied.valid.json",
    ROOT / "fixtures" / "external" / "guardrail-fabric" / "devsecops-workroom" / "unsafe-mutation-without-grant.denied.valid.json",
    ROOT / "fixtures" / "external" / "guardrail-fabric" / "devsecops-workroom" / "credential-sensitive.escalated.valid.json",
    ROOT / "fixtures" / "external" / "guardrail-fabric" / "devsecops-workroom" / "safe-read-only-probe.allowed.valid.json",
]
MUTATION_CLASSES = {
    "diagnostic_mutation",
    "reversible_mitigation",
    "irreversible_mutation",
    "credential_sensitive",
    "data_sensitive",
    "customer_visible",
    "destructive",
    "privileged_identity",
    "network_exposure",
    "production_change",
}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def main() -> int:
    problems: list[str] = []
    workroom = load(WORKROOM)
    guardrails = [load(path) for path in GUARDRAIL_FIXTURES]

    workroom_ref = workroom.get("workroom_id")
    lane = workroom.get("lane")
    incident_ref = workroom.get("source_refs", {}).get("incident_ref")
    topology_ref = workroom.get("source_refs", {}).get("topology_ref")
    grants = {grant.get("action_class"): grant for grant in workroom.get("action_grants", []) if isinstance(grant, dict)}
    remediation_plans = workroom.get("remediation_plans", [])

    for fixture in guardrails:
        fixture_id = fixture.get("fixture_id")
        ctx = fixture.get("workroom_context", {})
        if ctx.get("workroom_ref") != workroom_ref:
            problems.append(f"{fixture_id}: workroom_ref must match Workroom fixture")
        if ctx.get("lane") != lane:
            problems.append(f"{fixture_id}: lane must match Workroom fixture")
        if ctx.get("incident_ref") != incident_ref:
            problems.append(f"{fixture_id}: incident_ref must match Workroom fixture")
        if ctx.get("topology_ref") != topology_ref:
            problems.append(f"{fixture_id}: topology_ref must match Workroom fixture")

    by_class = {fixture.get("fixture_class"): fixture for fixture in guardrails}

    poisoned = by_class.get("poisoned_evidence", {})
    if poisoned.get("expected_decision") not in {"deny", "escalate"}:
        problems.append("poisoned evidence must deny or escalate")
    if poisoned.get("input", {}).get("contains_policy_override_attempt") is not True:
        problems.append("poisoned evidence fixture must contain override attempt")

    unsafe = by_class.get("unsafe_mutation_without_grant", {})
    if unsafe.get("expected_decision") != "deny":
        problems.append("unsafe mutation without grant must deny")
    if unsafe.get("input", {}).get("has_action_grant") is not False:
        problems.append("unsafe mutation fixture must model missing ActionGrant")
    if unsafe.get("input", {}).get("action_class") not in MUTATION_CLASSES:
        problems.append("unsafe mutation fixture must use mutation action class")

    credential = by_class.get("credential_sensitive_action", {})
    if credential.get("expected_decision") != "escalate":
        problems.append("credential-sensitive action must escalate")
    if credential.get("input", {}).get("requires_credential_access") is not True:
        problems.append("credential-sensitive fixture must require credential access")

    read_only = by_class.get("safe_read_only_probe", {})
    if read_only.get("expected_decision") != "allow":
        problems.append("safe read-only probe must allow")
    if read_only.get("input", {}).get("action_class") != "read_only":
        problems.append("safe read-only probe must use read_only action class")
    read_only_grant = grants.get("read_only")
    if not read_only_grant or read_only_grant.get("status") != "allowed" or read_only_grant.get("approval_required") is not False:
        problems.append("Workroom must include allowed read_only grant for safe read-only probe")

    production_grant = grants.get("production_change")
    if not production_grant:
        problems.append("Workroom must include production_change grant for high-risk candidate remediation")
    else:
        if production_grant.get("status") != "requires_human_approval":
            problems.append("Workroom production_change grant must require human approval")
        if production_grant.get("approval_required") is not True:
            problems.append("Workroom production_change grant must set approval_required true")

    for plan in remediation_plans:
        if plan.get("risk_class") in {"high", "critical"}:
            if not plan.get("required_action_grant_refs"):
                problems.append(f"{plan.get('plan_id')}: high/critical plan must require action grant refs")
            if plan.get("plan_status") == "executed":
                problems.append(f"{plan.get('plan_id')}: high/critical plan must not be executed in fixture")

    report = {
        "validator": "prophet-platform.workroom-guardrail-action-safety.validator.v1",
        "passed": not problems,
        "problems": problems,
        "inputs": {
            "workroom": str(WORKROOM.relative_to(ROOT)),
            "guardrails": [str(path.relative_to(ROOT)) for path in GUARDRAIL_FIXTURES],
        },
        "non_claims": [
            "Validator checks Workroom-to-Guardrail fixture posture only.",
            "Validator does not execute infrastructure.",
            "Validator does not inspect live production systems.",
            "Validator does not authorize remediation.",
            "Validator does not certify Signadot feature parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom Guardrail action safety")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
