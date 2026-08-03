from __future__ import annotations

import json
from pathlib import Path

from .validation import validate_json_file


VDT_PROFILE_SCHEMA = "schemas/vdt_profile.schema.json"
POLARITIES = {"higher_better", "lower_better"}

# A value-driver-tree run measures a projected value uplift from KPI levers; it is
# advisory measurement only and asserts no security/investment/settlement outcome.
REQUIRED_NON_GOALS = {
    "live_money_movement",
    "securities_issuance",
    "investment_advice",
    "deposit_taking",
    "external_token_issuance",
}


def load_vdt_profile(path: str) -> dict:
    """Load and validate a value-driver-tree profile fixture (measurement only)."""
    validate_json_file(path, VDT_PROFILE_SCHEMA)
    return json.loads(Path(path).read_text())


def _weight_index(weights: list[dict]) -> dict[tuple[str, str], float]:
    return {(w["driver"], w["domain"]): float(w["weight"]) for w in weights}


def improvement_fraction(delta_pct: float, polarity: str) -> float:
    """Value-positive improvement fraction of a KPI move.

    `higher_better` metrics (revenue, margin, occupancy) improve as they rise;
    `lower_better` metrics (unit cost, emissions, incident rate) improve as they
    fall, so a negative delta on them is a *positive* improvement.
    """
    if polarity not in POLARITIES:
        raise ValueError(f"unknown polarity '{polarity}' (expected higher_better|lower_better)")
    frac = float(delta_pct) / 100.0
    return frac if polarity == "higher_better" else -frac


def kpi_value_contribution(kpi: dict, weight_index: dict, enterprise_value_baseline: float) -> float:
    """Enterprise-value contribution of one KPI lever = improvement × cell weight × EV.

    The cell weight w[driver][domain] is the fraction of enterprise value carried
    by that (value-driver × capability-domain) intersection; improving the KPI
    that sits in the cell moves that fraction of value by the improvement amount.
    A KPI whose (driver, domain) cell is absent from the tensor contributes 0.
    """
    w = weight_index.get((kpi["driver"], kpi["domain"]), 0.0)
    imp = improvement_fraction(kpi["delta_pct"], kpi["polarity"])
    return imp * w * float(enterprise_value_baseline)


def summarize_vdt(data: dict) -> dict:
    """Deterministic value-driver-tree summary: per-KPI / per-driver / per-domain
    value uplift, the total, and the projected enterprise value."""
    ev = float(data["enterprise_value_baseline"])
    widx = _weight_index(data["weights"])

    per_kpi: list[dict] = []
    per_driver: dict[str, float] = {}
    per_domain: dict[str, float] = {}
    total = 0.0
    for kpi in data["kpis"]:
        contribution = kpi_value_contribution(kpi, widx, ev)
        per_kpi.append(
            {
                "kpi": kpi["kpi"],
                "driver": kpi["driver"],
                "domain": kpi["domain"],
                "delta_pct": float(kpi["delta_pct"]),
                "polarity": kpi["polarity"],
                "value_contribution": contribution,
            }
        )
        per_driver[kpi["driver"]] = per_driver.get(kpi["driver"], 0.0) + contribution
        per_domain[kpi["domain"]] = per_domain.get(kpi["domain"], 0.0) + contribution
        total += contribution

    boundary = data.get("measurement_boundary", {})
    non_goals = set(boundary.get("non_goals", []))

    return {
        "run_id": data["run_id"],
        "scenario": data["scenario"],
        "industry": data["industry"],
        "enterprise_value_baseline": ev,
        "driver_count": len(data["drivers"]),
        "domain_count": len(data["domains"]),
        "kpi_count": len(data["kpis"]),
        "weight_cell_count": len(widx),
        "weight_sum": sum(widx.values()),
        "per_kpi_contribution": per_kpi,
        "per_driver_uplift": per_driver,
        "per_domain_uplift": per_domain,
        "computed_total_value_uplift": total,
        "reported_total_value_uplift": float(data.get("reported_total_value_uplift", 0.0)),
        "computed_value_uplift_fraction": (total / ev) if ev else 0.0,
        "reported_value_uplift_fraction": float(data.get("reported_value_uplift_fraction", 0.0)),
        "projected_enterprise_value": ev + total,
        "measurement_boundary_mode": boundary.get("mode", ""),
        "required_non_goals_present": sorted(REQUIRED_NON_GOALS & non_goals),
        "missing_required_non_goals": sorted(REQUIRED_NON_GOALS - non_goals),
    }


def run_vdt(path: str) -> dict:
    """Load a value-driver-tree profile and return summary + profile."""
    data = load_vdt_profile(path)
    return {"summary": summarize_vdt(data), "profile": data}
