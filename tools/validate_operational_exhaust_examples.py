#!/usr/bin/env python3
"""Validate the repository's operational-exhaust example payloads.

This is a lightweight dependency-free shape check. It does not replace full JSON Schema
validation; it keeps examples honest in minimal CI/dev environments.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "operational-exhaust"

COMMON_REQUIRED = {
    "version",
    "event_id",
    "observed_at",
    "source_repo",
    "source_surface",
    "source_runtime",
    "environment_ref",
    "trace_ref",
    "projection_family",
}

TRADER_REQUIRED = {
    "version",
    "event_id",
    "observed_at",
    "strategy_run_ref",
    "model_ref",
    "feature_snapshot_ref",
    "market_window_ref",
    "risk_policy_ref",
    "order_intent_ref",
    "execution_ref",
    "venue_ref",
    "trace_ref",
    "projection_family",
}


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as exc:  # pragma: no cover - command-line diagnostics
        raise SystemExit(f"failed to parse {path}: {exc}") from exc


def require_fields(name: str, payload: dict, required: set[str]) -> list[str]:
    return sorted(field for field in required if field not in payload)


def main() -> int:
    checks = [
        (
            "operational_exhaust_observed.example.json",
            COMMON_REQUIRED,
            "market_data_operations",
        ),
        (
            "trader_agent_execution_observed.example.json",
            TRADER_REQUIRED,
            "trader_agent_execution",
        ),
    ]
    failed = False
    for filename, required, projection_family in checks:
        path = EXAMPLES / filename
        payload = read_json(path)
        missing = require_fields(filename, payload, required)
        if missing:
            print(f"[FAIL] {filename}: missing fields: {', '.join(missing)}", file=sys.stderr)
            failed = True
        if payload.get("projection_family") != projection_family:
            print(
                f"[FAIL] {filename}: projection_family={payload.get('projection_family')!r}, expected {projection_family!r}",
                file=sys.stderr,
            )
            failed = True
    if failed:
        return 1
    print("[OK] operational-exhaust examples passed lightweight shape checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
