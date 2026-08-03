from __future__ import annotations

import json
from pathlib import Path

from .validation import validate_json_file


IMPACT_VDT_SCHEMA = "schemas/impact_vdt.schema.json"

# An impact value-driver tree measures projected people-reach + cost-effectiveness
# from a fixed budget allocated across interventions. Advisory measurement only —
# it moves no money and commits no grant/procurement.
REQUIRED_NON_GOALS = {
    "live_money_movement",
    "grant_disbursement",
    "procurement_commitment",
    "investment_advice",
    "beneficiary_enrollment",
}


def load_impact_vdt(path: str) -> dict:
    """Load and validate an impact value-driver-tree fixture (measurement only)."""
    validate_json_file(path, IMPACT_VDT_SCHEMA)
    return json.loads(Path(path).read_text())


def intervention_people(iv: dict) -> dict:
    """People reached by one intervention at its allocation.

    people = (allocation_usd / 1e6) * people_per_$1M. Low/high bound the estimate;
    mid is their midpoint. The people-per-$1M yields are the intervention menu's
    cost-effectiveness numbers, so this is a linear budget → reach projection.
    """
    m = float(iv["allocation_usd"]) / 1_000_000.0
    low = m * float(iv["people_per_million_low"])
    high = m * float(iv["people_per_million_high"])
    mid = (low + high) / 2.0
    return {"low": low, "mid": mid, "high": high}


def summarize_impact_vdt(data: dict) -> dict:
    """Deterministic impact summary: per-intervention reach + cost-effectiveness,
    per-driver rollup, budget totals, blended cost-per-person, and an
    equity-weighted total."""
    budget = float(data["budget_usd"])
    per_intervention: list[dict] = []
    per_driver: dict[str, float] = {}
    total_low = total_mid = total_high = total_equity = 0.0
    allocated = 0.0

    for iv in data["interventions"]:
        people = intervention_people(iv)
        alloc = float(iv["allocation_usd"])
        eq = float(iv["equity_weight"])
        equity_adjusted = people["mid"] * eq
        cost_per_person = (alloc / people["mid"]) if people["mid"] else 0.0
        per_intervention.append(
            {
                "name": iv["name"],
                "driver": iv["driver"],
                "allocation_usd": alloc,
                "people_low": people["low"],
                "people_mid": people["mid"],
                "people_high": people["high"],
                "equity_weight": eq,
                "equity_adjusted_people": equity_adjusted,
                "cost_per_person_usd": cost_per_person,
                "people_per_million_mid": (float(iv["people_per_million_low"]) + float(iv["people_per_million_high"])) / 2.0,
            }
        )
        per_driver[iv["driver"]] = per_driver.get(iv["driver"], 0.0) + people["mid"]
        total_low += people["low"]
        total_mid += people["mid"]
        total_high += people["high"]
        total_equity += equity_adjusted
        allocated += alloc

    # Cost-effectiveness ranking (most people per $1M first).
    ranking = [x["name"] for x in sorted(per_intervention, key=lambda x: x["people_per_million_mid"], reverse=True)]

    boundary = data.get("measurement_boundary", {})
    non_goals = set(boundary.get("non_goals", []))

    return {
        "run_id": data["run_id"],
        "scenario": data["scenario"],
        "budget_usd": budget,
        "allocated_usd": allocated,
        "unallocated_usd": budget - allocated,
        "intervention_count": len(data["interventions"]),
        "driver_count": len(data["drivers"]),
        "per_intervention": per_intervention,
        "per_driver_people_mid": per_driver,
        "computed_total_people_low": total_low,
        "computed_total_people_mid": total_mid,
        "computed_total_people_high": total_high,
        "reported_total_people_mid": float(data.get("reported_total_people_mid", 0.0)),
        "computed_total_equity_adjusted_people": total_equity,
        "reported_total_equity_adjusted_people": float(data.get("reported_total_equity_adjusted_people", 0.0)),
        "blended_cost_per_person_usd": (allocated / total_mid) if total_mid else 0.0,
        "cost_effectiveness_ranking": ranking,
        "measurement_boundary_mode": boundary.get("mode", ""),
        "required_non_goals_present": sorted(REQUIRED_NON_GOALS & non_goals),
        "missing_required_non_goals": sorted(REQUIRED_NON_GOALS - non_goals),
    }


def run_impact_vdt(path: str) -> dict:
    """Load an impact value-driver-tree profile and return summary + profile."""
    data = load_impact_vdt(path)
    return {"summary": summarize_impact_vdt(data), "profile": data}
