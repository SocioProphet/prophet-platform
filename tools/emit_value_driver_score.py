#!/usr/bin/env python3
"""Score a Crystal Atlas downstream finding on value drivers (the value-driver seam).

Consumes a Crystal Atlas downstream finding (procurement substitution, diligence
risk pack, entitlement adjacency, clause comparison) and emits
`intel.value_driver.scored.v0` — an equity-weighted value-driver breakdown plus
an overall value score — so competitive-intelligence findings arrive quantified.

Actionable: with `--emit` it writes an event/receipt/payload bundle to the
platform state spine.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVICE = "value-driver-scorer"

# The four Crystal Atlas downstream findings this seam accepts (matches the strict
# source_event_type enum in intel.value_driver.scored.v0). Enforced before any
# write so append-only state is never polluted with an out-of-contract event.
ALLOWED_SOURCE_EVENT_TYPES = frozenset(
    {
        "contract.clauses.compared.v0",
        "procurement.substitution.recommended.v0",
        "entitlement.adjacency.inferred.v0",
        "diligence.risk.pack.generated.v0",
    }
)


class OutOfContractEvent(ValueError):
    """Raised when an event would violate the seam contract (fail-closed on emit)."""


def assert_emittable(event: dict[str, Any]) -> None:
    """Reject events that must not enter append-only state (spec D2/D11)."""
    src = event.get("source", {})
    t = src.get("source_event_type")
    if t not in ALLOWED_SOURCE_EVENT_TYPES:
        raise OutOfContractEvent(
            f"refusing to emit: source_event_type {t!r} is not one of {sorted(ALLOWED_SOURCE_EVENT_TYPES)}"
        )
    if not src.get("source_event_id"):
        raise OutOfContractEvent("refusing to emit: source.source_event_id must be non-empty")


def drivers_for(finding: dict[str, Any]) -> list[tuple[str, str, float, float]]:
    """Return (driver, kpi, score, equity_weight) tuples for a finding.

    Weights within each finding type sum to 1.0, so the overall score stays on a
    0..100 scale. An unknown type falls back to a single generic driver.
    """
    t = finding.get("source_event_type", "")
    if t == "procurement.substitution.recommended.v0":
        return [
            ("Cost Efficiency", "estimated_savings_pct", float(finding.get("estimated_savings_pct", 0.0)), 0.5),
            ("Switching Risk", "substitution_confidence", float(finding.get("substitution_confidence", 0.0)), 0.3),
            ("Continuity", "coverage_completeness", float(finding.get("coverage_completeness", 100.0)), 0.2),
        ]
    if t == "diligence.risk.pack.generated.v0":
        risk = float(finding.get("risk_score", 0.0))
        return [
            ("Risk Exposure", "risk_score_inverted", max(0.0, 100.0 - risk), 0.6),
            ("Coverage Completeness", "coverage_completeness", float(finding.get("coverage_completeness", 0.0)), 0.4),
        ]
    if t == "entitlement.adjacency.inferred.v0":
        return [("Expansion Potential", "adjacency_strength", float(finding.get("adjacency_strength", 0.0)), 1.0)]
    if t == "contract.clauses.compared.v0":
        return [("Change Materiality", "changed_families_pct", float(finding.get("changed_families_pct", 0.0)), 1.0)]
    return [("Finding Value", "value_score", float(finding.get("value_score", 0.0)), 1.0)]


def compute_scored_event(
    finding: dict[str, Any],
    *,
    subject: str,
    tenant_id: str = "socioprophet",
    producer: str = SERVICE,
) -> dict[str, Any]:
    """Build an intel.value_driver.scored.v0 payload from a Crystal Atlas finding."""
    tuples = drivers_for(finding)
    value_drivers = [
        {"driver": d, "kpi": k, "score": round(s, 2), "equity_weight": w}
        for (d, k, s, w) in tuples
    ]
    overall = round(sum(s * w for (_, _, s, w) in tuples), 2)
    return {
        "event_id": f"cav-vd-{uuid.uuid4().hex[:12]}",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "producer": producer,
        "subject": subject,
        "epistemic_level": finding.get("epistemic_level", "empirical"),
        "provenance": {
            "source": "crystal_atlas",
            "method": "downstream-finding-mapping",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        "source": {
            "source_event_type": finding.get("source_event_type", ""),
            "source_event_id": finding.get("source_event_id", ""),
        },
        "value_drivers": value_drivers,
        "overall_value_score": overall,
    }


def _state_root() -> Path:
    home = os.environ.get("SOCIOPROFIT_STATE_HOME")
    base = Path(home) if home else Path.home() / ".local" / "state"
    return base / "prophet-platform"


def emit(event: dict[str, Any]) -> str:
    # Fail-closed: never write an out-of-contract event to append-only state.
    assert_emittable(event)
    corr = event["event_id"]
    root = _state_root()
    for kind, payload, suffix in (
        ("payloads", event, "payload"),
        ("events", {"event_type": "intel.value_driver.scored.v0", "created_at": event["emitted_at"], "subject_ref": event["subject"]}, "event"),
        ("receipts", {"status": "succeeded", "action": "ScoreValueDrivers", "subject_ref": event["subject"], "created_at": event["emitted_at"]}, "receipt"),
    ):
        d = root / kind / SERVICE
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{corr}.{suffix}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return corr


def main() -> int:
    ap = argparse.ArgumentParser(description="Score a Crystal Atlas finding on value drivers.")
    ap.add_argument("--in", dest="in_file", required=True, help="Crystal Atlas downstream finding JSON.")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--emit", action="store_true")
    args = ap.parse_args()

    finding = json.loads(Path(args.in_file).read_text(encoding="utf-8"))
    event = compute_scored_event(finding, subject=args.subject)
    print(json.dumps(event, indent=2, sort_keys=True))
    if args.emit:
        try:
            print(f"emitted: {emit(event)}")
        except OutOfContractEvent as exc:
            print(f"NOT emitted: {exc}", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
