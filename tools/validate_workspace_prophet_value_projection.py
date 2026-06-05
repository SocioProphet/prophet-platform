#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "workspace-prophet" / "e2e" / "value-claim-projection-workspace-prophet-v0.json"

def main() -> int:
    try:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERR: failed to load value projection fixture: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    claim = data.get("value_claim", {})

    if data.get("source_claim_id") != claim.get("claim_id"):
        errors.append("source_claim_id must match value_claim.claim_id")
    if data.get("source_receipt_id") not in claim.get("receipt_ids", []):
        errors.append("source_receipt_id must be present in value_claim.receipt_ids")
    if claim.get("claim_type") != "value_claim":
        errors.append("claim_type must be value_claim")
    if claim.get("production_ready") is not False:
        errors.append("production_ready must be false")
    if claim.get("falsification_plan", {}).get("observation_window") != "fixture_validation_only":
        errors.append("observation_window must be fixture_validation_only")
    if claim.get("value_driver", {}).get("primary") != "productivity":
        errors.append("primary value driver must be productivity for this fixture")

    kq = claim.get("knowledge_quality", {})
    expected_k = round(
        float(kq.get("coverage", 0))
        * float(kq.get("coherence", 0))
        * float(kq.get("stability", 0))
        * float(kq.get("provenance", 0)),
        3,
    )
    if round(float(kq.get("k", -1)), 3) != expected_k:
        errors.append(f"knowledge_quality.k must equal rounded product {expected_k}")

    required_kpis = {"validated_control_loop_steps", "blocked_unapproved_action_classes"}
    actual_kpis = {item.get("kpi") for item in claim.get("kpi_mappings", [])}
    missing = sorted(required_kpis - actual_kpis)
    if missing:
        errors.append(f"missing KPI mappings: {missing}")

    if errors:
        print("ERR: Workspace PROPHET value projection validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print("Workspace PROPHET value projection validation passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
