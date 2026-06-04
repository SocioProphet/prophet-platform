#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "libs" / "go" / "tritrpcbridge" / "binding" / "binding.go"
API = ROOT / "apps" / "api" / "cmd" / "socioprophet-api" / "main.go"
GATEWAY = ROOT / "apps" / "gateway" / "cmd" / "tritrpc-gateway" / "main.go"
REQUEST = ROOT / "contracts" / "environment" / "validate-change-v2-request.example.json"

REQUIRED_BINDING = [
    'ValidateChangeService = "platform.validate_change.v2"',
    'ValidateChangeReq     = "ValidateChange.Environment.REQ"',
    'ValidateChangeRes     = "ValidateChange.Environment.RES"',
]
REQUIRED_API = [
    "handleValidateChange",
    "binding.ValidateChangeService",
    "binding.ValidateChangeReq",
    '"status": "environment_requested"',
    '"agentplane_synthetic_sandbox_run"',
    '"evidence_summary"',
    '"validation_evidence_state": "missing_evidence"',
    '"pr_readiness"',
    '"merge_allowed": false',
    '"required_evidence_state": "verified_receipt"',
    '"verified_receipt_required"',
    '"workroom_projection"',
    '"workroom_id": "workroom:devsecops:pre-merge:api-stub-missing-evidence"',
    '"runtime_parity_level": "contract_only"',
    '"event_type": "pre_merge_validation_failure"',
    '"decision_state": "blocked"',
    '"Projection does not execute live sandbox infrastructure."',
    '"Projection does not certify Signadot-style feature parity."',
    '"API stub does not execute live sandbox infrastructure."',
]
REQUIRED_GATEWAY = [
    'mux.HandleFunc("/v1/validate-change"',
    'mux.HandleFunc("/v1/workroom/report"',
    'mux.HandleFunc("/v1/workroom/report.md"',
    'mux.HandleFunc("/v1/workroom/runtime-parity-bridge"',
    "func validateChange(",
    "func serveStaticReport(",
    "binding.ValidateChangeService",
    "binding.ValidateChangeReq",
    "binding.ValidateChangeRes",
    "X-Workroom-Report-Mode",
    "X-Workroom-Non-Claim",
    "no-execution-no-remediation-no-signadot-parity",
    "WORKROOM_REPORT_JSON_PATH",
    "WORKROOM_REPORT_MARKDOWN_PATH",
    "WORKROOM_RUNTIME_PARITY_BRIDGE_PATH",
    "defaultWorkroomRuntimeParityBridge",
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

    result = {
        "validator": "prophet-platform.validate-change-v2.api-stub-smoke.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Smoke check does not execute live sandbox infrastructure.",
            "Smoke check does not certify Signadot-style runtime parity.",
            "Smoke check validates route/contract wiring, readiness fields, Workroom projection, fixture report route presence, and runtime parity bridge route presence only."
        ]
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": validate_change v2 API stub smoke")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
