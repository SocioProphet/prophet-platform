#!/usr/bin/env python3
"""Emit example operational-exhaust events for local smoke checks.

This helper intentionally emits deterministic example JSON rather than connecting to
runtime services. Real emitters should populate the same fields from service context,
trace context, policy/evidence receipts, and trader-agent execution state.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "operational-exhaust"


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


def main() -> int:
    events = [
        load("operational_exhaust_observed.example.json"),
        load("trader_agent_execution_observed.example.json"),
    ]
    print(json.dumps(events, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
