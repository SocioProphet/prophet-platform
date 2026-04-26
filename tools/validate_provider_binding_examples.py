#!/usr/bin/env python3
"""Validate ProviderBinding examples without third-party dependencies."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "specs" / "brokerage" / "events" / "examples" / "provider-binding.example.json"

REQUIRED = [
    "binding_id",
    "service_class",
    "provider_class",
    "provider_id",
    "blueprint_id",
    "policy_pack_ids",
    "portability_tier",
    "evidence_profile_id",
    "cost_meter_profile_id",
    "continuity_profile_id",
    "exit_plan_ref",
    "approval_state",
    "owner",
]

PROVIDER_CLASSES = {
    "internal-shared-service",
    "private-cloud",
    "public-cloud",
    "saas",
    "partner-managed-service",
    "legacy-adapter",
}

PORTABILITY_TIERS = {
    "P0-governed-native",
    "P1-contract-compatible",
    "P2-blueprint-portable",
    "P3-operationally-portable",
    "P4-exit-tested",
}

APPROVAL_STATES = {"Draft", "UnderReview", "Approved", "Suspended", "Retired"}


def main() -> int:
    if not EXAMPLE.exists():
        print(f"Missing example: {EXAMPLE}")
        return 1

    with EXAMPLE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    missing = [key for key in REQUIRED if key not in payload]
    if missing:
        print("ProviderBinding example missing required keys:")
        for key in missing:
            print(f" - {key}")
        return 1

    if payload["provider_class"] not in PROVIDER_CLASSES:
        print("Invalid provider_class")
        return 1
    if payload["portability_tier"] not in PORTABILITY_TIERS:
        print("Invalid portability_tier")
        return 1
    if payload["approval_state"] not in APPROVAL_STATES:
        print("Invalid approval_state")
        return 1
    if not isinstance(payload["policy_pack_ids"], list) or not payload["policy_pack_ids"]:
        print("policy_pack_ids must be a non-empty list")
        return 1

    print("ProviderBinding example passes required checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
