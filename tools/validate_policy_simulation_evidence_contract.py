#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "contracts" / "policy-simulation"
REQUIRED_NON_CLAIM_FRAGMENTS = [
    "does not execute",
    "does not import",
    "does not authorize live policy automation",
    "does not release economic value",
    "does not claim fairness",
]


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture must be an object: {path}")
    return data


def check(check_id: str, passed: bool, diagnostics: list[str] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "diagnostics": diagnostics or []}


def semantic_diagnostics(data: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    profile = data.get("profile", {})
    triparty = data.get("triparty", {})
    authority_refs = data.get("authorityRefs", {})
    non_claims = data.get("nonClaims", [])

    if profile.get("donorRuntimeDependency") is not False:
        diagnostics.append("donorRuntimeDependency must be false")
    if profile.get("releaseAuthority") != "advisory_only":
        diagnostics.append("releaseAuthority must be advisory_only")

    lambda_evid = float(triparty.get("lambdaEvid", 0.0))
    lambda_admit = float(triparty.get("lambdaAdmit", 0.0))
    lambda_release = float(triparty.get("lambdaRelease", 0.0))
    residual = float(triparty.get("residual", 0.0))

    for field_name, value in [
        ("lambdaEvid", lambda_evid),
        ("lambdaAdmit", lambda_admit),
        ("lambdaRelease", lambda_release),
        ("residual", residual),
    ]:
        if value < 0.0:
            diagnostics.append(f"triparty.{field_name} must be nonnegative")

    if lambda_admit > lambda_evid:
        diagnostics.append("lambdaAdmit cannot exceed lambdaEvid")
    if lambda_release > lambda_admit:
        diagnostics.append("lambdaRelease cannot exceed lambdaAdmit")
    if abs((lambda_evid - lambda_release) - residual) > 1e-9:
        diagnostics.append("residual must equal lambdaEvid - lambdaRelease")

    if not authority_refs.get("adoptionRegistry"):
        diagnostics.append("authorityRefs.adoptionRegistry is required")
    if not authority_refs.get("learningReceipt"):
        diagnostics.append("authorityRefs.learningReceipt is required")
    if not authority_refs.get("measurementContract"):
        diagnostics.append("authorityRefs.measurementContract is required")
    if not authority_refs.get("platformContract"):
        diagnostics.append("authorityRefs.platformContract is required")

    joined_non_claims = " ".join(str(item) for item in non_claims).lower()
    for fragment in REQUIRED_NON_CLAIM_FRAGMENTS:
        if fragment not in joined_non_claims:
            diagnostics.append(f"nonClaims missing boundary fragment: {fragment}")

    return diagnostics


def validate_fixture(path: Path) -> list[dict[str, Any]]:
    data = load(path)
    results = [
        check(f"{path.name}:schema-version", data.get("schemaVersion") == "1.0"),
        check(f"{path.name}:receipt-type", data.get("receiptType") == "policy_simulation_evidence_receipt"),
        check(f"{path.name}:receipt-id", str(data.get("receiptId", "")).startswith("policy-simulation-evidence:")),
        check(f"{path.name}:status", data.get("status") in {"accepted_for_review", "rejected", "blocked"}),
        check(f"{path.name}:source", bool(data.get("source", {}).get("repo")) and bool(data.get("source", {}).get("artifactRef"))),
        check(f"{path.name}:profile", bool(data.get("profile", {}).get("profileId")) and bool(data.get("profile", {}).get("runId"))),
        check(f"{path.name}:triparty", "triparty" in data),
        check(f"{path.name}:authority-refs", bool(data.get("authorityRefs"))),
        check(f"{path.name}:non-claims", bool(data.get("nonClaims"))),
    ]
    diagnostics = semantic_diagnostics(data)
    actual = "fail" if diagnostics else "pass"
    expected = "fail" if ".rejected-" in path.name or path.name.startswith("bad-") else "pass"
    results.append(check(f"{path.name}:semantic-expected-{expected}", actual == expected, diagnostics))
    return results


def main() -> int:
    results: list[dict[str, Any]] = []
    fixtures = sorted(FIXTURE_DIR.glob("evidence-receipt.*.example.json"))
    if not fixtures:
        raise SystemExit("No policy simulation evidence fixtures found")
    for path in fixtures:
        results.extend(validate_fixture(path))
    passed = all(item["passed"] for item in results)
    print(json.dumps({"validator": "prophet-platform.policy-simulation-evidence.validator.v1", "passed": passed, "results": results}, indent=2, sort_keys=True))
    print(("PASS" if passed else "FAIL") + ": policy simulation evidence fixtures")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
