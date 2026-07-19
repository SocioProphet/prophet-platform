#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "apps" / "socioprophet-web" / "src" / "components" / "DevSecOpsWorkroomReportCard.vue"
# client-vue (the deployed cockpit since Phase 3) is router-based: App.vue is the shell and each
# surface is its own routed page. The Workroom card is wired into its own route
# (/workstation/devsecops) rather than the old single-page App.vue, so the wiring check reads that
# page. The card itself is byte-for-byte unchanged, so the governance contract still holds.
APP = ROOT / "apps" / "socioprophet-web" / "src" / "pages" / "WorkstationDevSecOps.vue"
GATEWAY = ROOT / "apps" / "gateway" / "cmd" / "tritrpc-gateway" / "main.go"

REQUIRED_COMPONENT = [
    "type RuntimeParityBridge",
    "runtimeBridge = ref<RuntimeParityBridge | null>(null)",
    "fetch('/api/v1/workroom/runtime-parity-bridge')",
    "bridgeLaneEntries",
    "runtimeBridge.decision_state",
    "runtimeBridge.observed_evidence.fogstack_parity_status",
    "runtimeBridge.observed_evidence.svf_adapter_readiness_status",
    "runtimeBridge.observed_evidence.svf_adapter_merge_readiness",
    "runtimeBridge.non_certified_claims",
    "Runtime parity bridge",
    "Not certified",
]
REQUIRED_APP = [
    "import DevSecOpsWorkroomReportCard",
    "<DevSecOpsWorkroomReportCard />",
]
REQUIRED_GATEWAY = [
    'mux.HandleFunc("/v1/workroom/runtime-parity-bridge"',
    "WORKROOM_RUNTIME_PARITY_BRIDGE_PATH",
    "defaultWorkroomRuntimeParityBridge",
]
FORBIDDEN_COMPONENT = [
    "signadot_vendor_parity_certified",
    "production_readiness_certified",
    "live_apply_authorized",
    "cluster_mutation_allowed",
]


def require(text: str, needle: str, surface: str, problems: list[str]) -> None:
    if needle not in text:
        problems.append(f"missing {needle!r} in {surface}")


def forbid(text: str, needle: str, surface: str, problems: list[str]) -> None:
    if needle in text:
        problems.append(f"forbidden {needle!r} in {surface}")


def main() -> int:
    problems: list[str] = []
    component = COMPONENT.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")

    for needle in REQUIRED_COMPONENT:
        require(component, needle, str(COMPONENT.relative_to(ROOT)), problems)
    for needle in REQUIRED_APP:
        require(app, needle, str(APP.relative_to(ROOT)), problems)
    for needle in REQUIRED_GATEWAY:
        require(gateway, needle, str(GATEWAY.relative_to(ROOT)), problems)
    for needle in FORBIDDEN_COMPONENT:
        forbid(component, needle, str(COMPONENT.relative_to(ROOT)), problems)

    report = {
        "validator": "prophet-platform.workroom-runtime-parity-ui-component.validator.v1",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Validator checks static UI wiring only.",
            "Validator does not execute the browser UI.",
            "Validator does not call Signadot.",
            "Validator does not execute Kubernetes workloads.",
            "Validator does not certify full Signadot-style feature parity."
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": Workroom runtime parity UI component")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
