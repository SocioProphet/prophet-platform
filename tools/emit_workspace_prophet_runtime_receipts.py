#!/usr/bin/env python3
"""Emit non-production WorkspaceOperation + PROPHET runtime receipt fixtures.

This script is deterministic and fixture-backed. It does not perform external
actions. It converts the local WorkspaceOperation + ScopedCapability fixture pack
into a generated receipt pack that downstream ledger/search/readiness surfaces
can consume as runtime-observed fixture evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "workspace-prophet" / "e2e" / "workspace-operation-prophet-membrane-v0.json"
DEFAULT_OUTPUT = ROOT / "build" / "workspace-prophet" / "runtime-receipts.generated.json"
NOW = datetime(2026, 6, 4, 0, 0, 0, tzinfo=timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate_scenario(scenario: dict[str, Any]) -> tuple[str, list[str]]:
    operation = scenario.get("operation") or {}
    capability = scenario.get("scoped_capability")
    requested_verb = scenario.get("requested_verb")
    reasons: list[str] = []

    if capability is None:
        return "blocked", ["missing_scoped_capability"]

    if capability.get("fail_closed") is not True:
        reasons.append("capability_not_fail_closed")
    if capability.get("capability_id") != operation.get("capability_profile_id"):
        reasons.append("capability_id_mismatch")

    binding = capability.get("workspace_operation_binding") or {}
    if binding.get("operation_id") != operation.get("operation_id"):
        reasons.append("operation_binding_mismatch")
    if binding.get("operation_type") != operation.get("operation_type"):
        reasons.append("operation_type_binding_mismatch")

    actor = operation.get("actor") or {}
    subject = capability.get("subject") or {}
    if actor.get("actor_id") != subject.get("actor_id") or actor.get("actor_type") != subject.get("actor_type"):
        reasons.append("actor_subject_mismatch")

    if requested_verb not in capability.get("verbs", []):
        reasons.append("verb_not_allowed")

    if not (parse_time(capability["valid_from"]) <= NOW <= parse_time(capability["expires_at"])):
        reasons.append("expired_scoped_capability")

    if reasons:
        return "blocked", reasons

    return "completed", [
        "scoped_capability_present",
        "scoped_capability_valid",
        "operation_binding_match",
        "verb_allowed",
    ]


def receipt_for(scenario: dict[str, Any]) -> dict[str, Any]:
    operation = scenario["operation"]
    capability = scenario.get("scoped_capability") or {}
    result_state, reason_codes = evaluate_scenario(scenario)
    policy_decision = "allow" if result_state == "completed" else "block"
    capability_id = capability.get("capability_id") or "missing"
    operation_id = operation["operation_id"]

    return {
        "schema_version": "0.1.0",
        "receipt_id": f"receipt_{operation_id}",
        "operation_id": operation_id,
        "capability_id": capability_id,
        "actor": operation.get("actor", {}),
        "action": {
            "verb": scenario.get("requested_verb"),
            "resource_id": (capability.get("resource") or operation.get("source") or {}).get("resource_id") or operation.get("source", {}).get("ref_id"),
            "resource_type": (capability.get("resource") or {}).get("resource_type") or operation.get("source", {}).get("ref_type"),
            "purpose": capability.get("purpose", "fixture-backed workspace prophet membrane validation"),
        },
        "policy_decision": policy_decision,
        "result_state": result_state,
        "reason_codes": reason_codes,
        "telemetry_plane": (capability.get("receipt_requirements") or {}).get("telemetry_plane", "developer_diagnostics"),
        "retention_class": (capability.get("receipt_requirements") or {}).get("retention_class", "fixture_receipt"),
        "created_at": operation.get("updated_at") or "2026-06-04T00:00:10Z",
        "evidence_ids": [operation_id, capability_id],
        "source_ids": ["SRC-0006"],
        "receipt_hash": f"sha256:{operation_id}-{result_state}-fixture",
        "metadata": {
            "scenario_id": scenario.get("scenario_id"),
            "fixture_generated": True,
            "production_ready": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(FIXTURE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    fixture = load_json(Path(args.fixture))
    receipts = [receipt_for(scenario) for scenario in fixture.get("scenarios", [])]
    output = {
        "schema_version": "0.1.0",
        "scenario_pack_id": "workspace_operation_prophet_runtime_receipts_v0",
        "production_ready": False,
        "generated_at": "2026-06-04T00:00:10Z",
        "receipts": receipts,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(receipts)} Workspace PROPHET runtime receipt(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
