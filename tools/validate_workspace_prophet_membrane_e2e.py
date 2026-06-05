#!/usr/bin/env python3
"""Validate local WorkspaceOperation + PROPHET membrane E2E fixtures.

This validator is intentionally deterministic and fixture-backed. It proves that
Prophet Platform can consume the canonical contract shape without becoming the
contract authority.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "workspace-prophet" / "e2e" / "workspace-operation-prophet-membrane-v0.json"
NOW = datetime(2026, 6, 4, 0, 0, 0, tzinfo=timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def evaluate_scenario(scenario: dict[str, Any]) -> tuple[str, list[str]]:
    operation = scenario.get("operation") or {}
    capability = scenario.get("scoped_capability")
    requested_verb = scenario.get("requested_verb")
    reason_codes: list[str] = []
    errors: list[str] = []

    if not operation.get("operation_id"):
        errors.append("operation_id is required")
    if not operation.get("operation_type"):
        errors.append("operation_type is required")
    if not operation.get("actor", {}).get("actor_id"):
        errors.append("operation actor is required")

    if capability is None:
        reason_codes.append("missing_scoped_capability")
        return "blocked", reason_codes + errors

    require(capability.get("fail_closed") is True, "capability must fail closed", errors)
    require(capability.get("capability_id") == operation.get("capability_profile_id"), "operation capability_profile_id must match capability_id", errors)

    binding = capability.get("workspace_operation_binding") or {}
    require(binding.get("required") is True, "workspace operation binding must be required", errors)
    require(binding.get("operation_id") == operation.get("operation_id"), "capability operation_id binding mismatch", errors)
    require(binding.get("operation_type") == operation.get("operation_type"), "capability operation_type binding mismatch", errors)

    actor = operation.get("actor") or {}
    subject = capability.get("subject") or {}
    require(actor.get("actor_id") == subject.get("actor_id"), "operation actor_id must match capability subject", errors)
    require(actor.get("actor_type") == subject.get("actor_type"), "operation actor_type must match capability subject", errors)

    if requested_verb not in capability.get("verbs", []):
        reason_codes.append("verb_not_allowed")

    try:
        valid_from = parse_time(capability["valid_from"])
        expires_at = parse_time(capability["expires_at"])
        if not (valid_from <= NOW <= expires_at):
            reason_codes.append("expired_scoped_capability")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"invalid capability time window: {exc}")

    if errors:
        reason_codes.extend(errors)
        return "blocked", reason_codes

    if reason_codes:
        return "blocked", reason_codes

    return "allowed", [
        "scoped_capability_present",
        "scoped_capability_valid",
        "operation_binding_match",
        "verb_allowed",
    ]


def main() -> int:
    if not FIXTURE.exists():
        raise SystemExit(f"missing fixture: {FIXTURE}")

    pack = load_json(FIXTURE)
    scenarios = pack.get("scenarios") or []
    if not scenarios:
        raise SystemExit("fixture pack contains no scenarios")

    failures: list[str] = []
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        actual_result, actual_reasons = evaluate_scenario(scenario)
        expected_result = scenario.get("expected_result")
        expected_reasons = scenario.get("expected_receipt", {}).get("reason_codes") or scenario.get("expected_reason_codes") or []

        if actual_result != expected_result:
            failures.append(f"{scenario_id}: expected result {expected_result}, got {actual_result}")
        missing = [reason for reason in expected_reasons if reason not in actual_reasons]
        if missing:
            failures.append(f"{scenario_id}: missing expected reason codes {missing}; actual={actual_reasons}")

    if failures:
        print("Workspace PROPHET membrane E2E validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Validated {len(scenarios)} WorkspaceOperation + PROPHET membrane scenario(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
