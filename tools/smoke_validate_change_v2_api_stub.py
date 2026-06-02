#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "libs" / "go" / "tritrpcbridge" / "binding" / "binding.go"
API = ROOT / "apps" / "api" / "cmd" / "socioprophet-api" / "main.go"
GATEWAY = ROOT / "apps" / "gateway" / "cmd" / "tritrpc-gateway" / "main.go"
REQUEST = ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json"
EXPORTED_RECEIPT_REQUEST = ROOT / "contracts" / "environment" / "validate-change-v2-request.exported-sociosphere-receipt.example.json"

REQUIRED_BINDING = [
    'ValidateChangeService = "platform.validate_change.v2"',
    'ValidateChangeReq     = "ValidateChange.Environment.REQ"',
    'ValidateChangeRes     = "ValidateChange.Environment.RES"',
]
REQUIRED_API = [
    "handleValidateChange",
    "buildValidateChangeResponse",
    "exported_sociosphere_receipt",
    "binding.ValidateChangeService",
    "binding.ValidateChangeReq",
    '"status": responseStatus',
    '"agentplane_synthetic_sandbox_run"',
    '"evidence_summary"',
    '"validation_evidence_state": evidenceState',
    '"verified_receipt"',
    '"failed_receipt"',
    '"stale_receipt"',
    '"run_refs": runRefs',
    '"agentplane:sandbox-run:exported-sociosphere-receipt"',
    '"pr_readiness"',
    '"merge_allowed": mergeAllowed',
    '"required_evidence_state": "verified_receipt"',
    '"verified_receipt_required"',
    '"API stub does not execute live sandbox infrastructure."',
    '"API stub consumes exported Sociosphere receipt state only."',
]
REQUIRED_GATEWAY = [
    'mux.HandleFunc("/v1/validate-change"',
    "func validateChange(",
    "binding.ValidateChangeService",
    "binding.ValidateChangeReq",
    "binding.ValidateChangeRes",
]


def require(text: str, needle: str, surface: str, problems: list[str]) -> None:
    if needle not in text:
        problems.append(f"missing {needle!r} in {surface}")


def main() -> int:
    problems: list[str] = []
    binding = BINDING.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    exported_request = json.loads(EXPORTED_RECEIPT_REQUEST.read_text(encoding="utf-8"))

    for needle in REQUIRED_BINDING:
        require(binding, needle, str(BINDING.relative_to(ROOT)), problems)
    for needle in REQUIRED_API:
        require(api, needle, str(API.relative_to(ROOT)), problems)
    for needle in REQUIRED_GATEWAY:
        require(gateway, needle, str(GATEWAY.relative_to(ROOT)), problems)

    if request.get("execution", {}).get("executor_plane") != "AgentPlane":
        problems.append("request fixture executor_plane must be AgentPlane")
    if request.get("environment_request", {}).get("requested_isolation_class") != "synthetic_no_network":
        problems.append("request fixture must remain synthetic_no_network")

    receipt = exported_request.get("exported_sociosphere_receipt", {})
    if receipt.get("verification", {}).get("status") != "verified":
        problems.append("exported Sociosphere receipt request fixture must carry verification.status verified")
    if not str(receipt.get("receipt_id", "")).startswith("svf:receipt:"):
        problems.append("exported Sociosphere receipt request fixture must carry svf:receipt id")
    if not str(receipt.get("run_ref", "")).startswith("svf:run:"):
        problems.append("exported Sociosphere receipt request fixture must carry svf:run ref")
    if exported_request.get("execution", {}).get("executor_plane") != "AgentPlane":
        problems.append("exported receipt request fixture executor_plane must be AgentPlane")

    result = {
        "validator": "prophet-platform.validate-change-v2.api-stub-smoke.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Smoke check does not execute live sandbox infrastructure.",
            "Smoke check does not certify Signadot-style runtime parity.",
            "Smoke check validates route/contract wiring and readiness-field presence only.",
            "Smoke check validates exported Sociosphere receipt request fixture shape only."
        ]
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": validate_change v2 API stub smoke")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
