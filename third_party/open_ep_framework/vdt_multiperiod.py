from __future__ import annotations

"""Multi-period value-driver tree — projects the single-period VDT identity over a horizon.

The single-period engine (``vdt.summarize_vdt``) measures a one-shot enterprise-value uplift from
KPI levers. This module extends the SAME identity across ``horizon_years`` periods so a scenario can
be modelled through time, with two accumulation modes per KPI and an optional discounted present
value of the uplift stream. It reuses ``vdt`` primitives (``_weight_index``, ``improvement_fraction``)
so the value math is not forked — it is the single-period identity compounded per period.

Accumulation modes (per KPI, field ``accumulation``; default ``step``):
  - ``compounding``  the lever recurs each period and compounds — cumulative fraction at period t is
                     ``(1 + f)**t - 1`` (e.g. same-store sales growth, network rollout).
  - ``step``         the lever is a permanent one-time improvement realised in period 1 and held —
                     cumulative fraction is ``f`` for every t >= 1 (e.g. a margin/cost reset).

Advisory measurement only; the measurement_boundary / non_goals of the input profile are preserved.
"""

from .vdt import POLARITIES, REQUIRED_NON_GOALS, _weight_index, improvement_fraction, load_vdt_profile

ACCUMULATION_MODES = {"compounding", "step"}


def _cumulative_fraction(base_fraction: float, mode: str, t: int) -> float:
    """Cumulative improvement fraction of a KPI at period t (1-indexed)."""
    if mode == "compounding":
        return (1.0 + base_fraction) ** t - 1.0
    return base_fraction  # step: realised in period 1, held flat thereafter


def summarize_vdt_multiperiod(data: dict) -> dict:
    """Project the value-driver tree over ``horizon_years`` periods.

    Extends the single-period profile with optional top-level ``horizon_years`` (default 1) and
    ``discount_rate`` (default 0.0), and optional per-KPI ``accumulation`` (default ``step``)."""
    ev = float(data["enterprise_value_baseline"])
    widx = _weight_index(data["weights"])
    horizon = int(data.get("horizon_years", 1))
    if horizon < 1:
        raise ValueError(f"horizon_years must be >= 1 (got {horizon})")
    discount = float(data.get("discount_rate", 0.0))

    specs = []
    for kpi in data["kpis"]:
        if kpi["polarity"] not in POLARITIES:
            raise ValueError(f"unknown polarity '{kpi['polarity']}'")
        mode = kpi.get("accumulation", "step")
        if mode not in ACCUMULATION_MODES:
            raise ValueError(f"unknown accumulation '{mode}' (expected compounding|step)")
        specs.append(
            {
                "kpi": kpi["kpi"],
                "driver": kpi["driver"],
                "domain": kpi["domain"],
                "delta_pct": float(kpi["delta_pct"]),
                "polarity": kpi["polarity"],
                "accumulation": mode,
                "base_fraction": improvement_fraction(kpi["delta_pct"], kpi["polarity"]),
                "weight": widx.get((kpi["driver"], kpi["domain"]), 0.0),
            }
        )

    periods: list[dict] = []
    prev_total = 0.0
    pv_uplift = 0.0
    for t in range(1, horizon + 1):
        per_kpi: list[dict] = []
        per_driver: dict[str, float] = {}
        total = 0.0
        for s in specs:
            contribution = _cumulative_fraction(s["base_fraction"], s["accumulation"], t) * s["weight"] * ev
            total += contribution
            per_driver[s["driver"]] = per_driver.get(s["driver"], 0.0) + contribution
            per_kpi.append(
                {
                    "kpi": s["kpi"],
                    "driver": s["driver"],
                    "domain": s["domain"],
                    "delta_pct": s["delta_pct"],
                    "polarity": s["polarity"],
                    "accumulation": s["accumulation"],
                    "value_contribution": contribution,
                }
            )
        incremental = total - prev_total
        pv_uplift += incremental / ((1.0 + discount) ** t)
        periods.append(
            {
                "year": t,
                "per_kpi_contribution": per_kpi,
                "per_driver_uplift": per_driver,
                "total_value_uplift": total,
                "incremental_value_uplift": incremental,
                "value_uplift_fraction": (total / ev) if ev else 0.0,
                "projected_enterprise_value": ev + total,
            }
        )
        prev_total = total

    terminal = periods[-1]
    boundary = data.get("measurement_boundary", {})
    non_goals = set(boundary.get("non_goals", []))

    return {
        "run_id": data["run_id"],
        "scenario": data["scenario"],
        "industry": data["industry"],
        "enterprise_value_baseline": ev,
        "horizon_years": horizon,
        "discount_rate": discount,
        "periods": periods,
        "terminal_total_value_uplift": terminal["total_value_uplift"],
        "terminal_value_uplift_fraction": terminal["value_uplift_fraction"],
        "terminal_projected_enterprise_value": terminal["projected_enterprise_value"],
        "present_value_of_uplift": pv_uplift,
        "measurement_boundary_mode": boundary.get("mode", ""),
        "required_non_goals_present": sorted(REQUIRED_NON_GOALS & non_goals),
        "missing_required_non_goals": sorted(REQUIRED_NON_GOALS - non_goals),
    }


def run_vdt_multiperiod(path: str) -> dict:
    """Load a value-driver-tree profile and return the multi-period summary + profile."""
    data = load_vdt_profile(path)
    return {"summary": summarize_vdt_multiperiod(data), "profile": data}
