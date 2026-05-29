#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "security" / "adversarial-scenario-ref.schema.json"
EXAMPLE = ROOT / "contracts" / "security" / "adversarial-scenario-ref.example.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, detail=None):
    return {"check": name, "passed": bool(ok), "detail": detail or []}


def main() -> int:
    schema = load(SCHEMA)
    example = load(EXAMPLE)
    out = []

    out.append(check("schema-version", example.get("schemaVersion") == "0.1.0"))
    out.append(check("scenario-ref", str(example.get("scenarioRef", "")).startswith("adversarial-scenario:")))
    out.append(check("source-repo", example.get("source", {}).get("scenarioRepo") == "SocioProphet/SCOPE-D"))
    out.append(check("binding-reference-only", example.get("bindingMode") == "reference_only"))

    platform_use = example.get("platformUse", {})
    out.append(check("platform-no-runtime-execution", platform_use.get("runtimeExecution") is False))
    out.append(check("platform-no-report-export", platform_use.get("reportExport") is False))
    out.append(check("platform-no-memory-writeback", platform_use.get("memoryWriteback") is False))
    out.append(check("platform-no-claim-promotion", platform_use.get("claimPromotion") is False))

    safety = example.get("safetyBoundary", {})
    out.append(check("safety-non-production", safety.get("nonProductionOnly") is True))
    for key in ["liveTargetAccess", "credentialAccess", "payloadDelivery", "stateMutation", "destructiveBehavior", "externalDelivery"]:
        out.append(check(f"safety-{key}-false", safety.get(key) is False))

    authority = example.get("authority", {})
    for key in ["runtimeAuthority", "procedureExecutionAuthority", "engagementAuthorizationAuthority", "activationAllowed"]:
        out.append(check(f"authority-{key}-false", authority.get(key) is False))

    out.append(check("evidence-refs", isinstance(example.get("evidenceRefs"), list) and len(example["evidenceRefs"]) > 0))
    out.append(check("runtime-decision-receipts", isinstance(example.get("runtimeDecisionReceiptRefs"), list) and len(example["runtimeDecisionReceiptRefs"]) > 0))
    out.append(check("policy-refs", isinstance(example.get("policyRefs"), list) and len(example["policyRefs"]) > 0))
    non_claims = set(example.get("semanticNonClaims", []))
    out.append(check("non-claims-no-execution", "does_not_execute_attack_procedure" in non_claims))
    out.append(check("non-claims-no-engagement", "does_not_authorize_engagement" in non_claims))
    out.append(check("non-claims-no-memory-writeback", "does_not_promote_memory_writeback" in non_claims))

    schema_required = set(schema.get("required", []))
    example_keys = set(example.keys())
    out.append(check("schema-required-covered", schema_required <= example_keys, [sorted(schema_required - example_keys)]))

    passed = all(item["passed"] for item in out)
    result = {"validator": "adversarial_scenario_ref.v0.1", "passed": passed, "results": out}
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        print("FAIL: adversarial scenario reference contract", file=sys.stderr)
        return 1
    print("PASS: adversarial scenario reference contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
