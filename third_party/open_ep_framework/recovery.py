from .domain import RecoverySurfaceInputs

_MACRO = {"benign": 0.03, "base": 0.0, "stressed": -0.06, "crisis": -0.12}
_LIQ = {"normal": 0.0, "tight": -0.03, "frozen": -0.08}

def planning_recovery(surface: RecoverySurfaceInputs) -> float:
    base = 0.15 + 0.35 * surface.seniority + 0.25 * surface.collateral_quality + 0.15 * surface.jurisdiction_score
    base += _MACRO.get(surface.macro_regime, 0.0) + _LIQ.get(surface.liquidity_regime, 0.0)
    horizon_drag = min(surface.workout_horizon_days / 3650.0, 0.25)
    return max(0.0, min(0.95, base - horizon_drag))

def market_implied_recovery(surface: RecoverySurfaceInputs) -> float:
    rp = 0.05 + 0.25 * surface.market_state_price
    return max(0.0, min(0.95, planning_recovery(surface) - rp))

def recovery_wedge(surface: RecoverySurfaceInputs) -> float:
    """RR^Q - RR^P (typically negative)."""
    return market_implied_recovery(surface) - planning_recovery(surface)
