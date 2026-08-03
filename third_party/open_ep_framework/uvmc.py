import math
from functools import reduce
from operator import mul
from typing import Iterable, Mapping, Sequence


ComponentMap = Mapping[str, float]


def _require_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")


def knowledge_strict(coverage: float, quality: float, stability: float, provenance: float) -> float:
    """Strict bottleneck knowledge score: K = C * Q * S * P."""
    components = {
        "coverage": coverage,
        "quality": quality,
        "stability": stability,
        "provenance": provenance,
    }
    for name, value in components.items():
        _require_unit_interval(name, value)
    return coverage * quality * stability * provenance


def knowledge_geometric(components: ComponentMap, weights: ComponentMap) -> float:
    """Weighted geometric knowledge score for continuous ranking.

    Components must be bounded to [0, 1]. Weights must be non-negative and sum
    to one. A zero component with positive weight produces a zero score, which
    keeps the geometric score conservative without making all weights equal.
    """
    if set(components) != set(weights):
        raise ValueError("components and weights must have identical keys")
    total_weight = sum(weights.values())
    if not math.isclose(total_weight, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("knowledge weights must sum to 1")
    score = 1.0
    for name, value in components.items():
        _require_unit_interval(name, value)
        weight = weights[name]
        if weight < 0.0:
            raise ValueError("knowledge weights must be non-negative")
        score *= value**weight
    _require_unit_interval("knowledge score", score)
    return score


def adjusted_hurdle_rate(
    base_cost_of_capital: float,
    risk_spread: float,
    provenance_penalty: float,
    knowledge_credit: float,
    operational_uncertainty_spread: float = 0.0,
    non_diversifiable_risk_floor: float = 0.0,
) -> float:
    """Compute sign-safe UVMC hurdle rate.

    Knowledge credit can reduce uncertainty load. It cannot erase base cost of
    capital, hard risk floors, or governed non-diversifiable risk.
    """
    if knowledge_credit < 0.0:
        raise ValueError("knowledge_credit must be non-negative")
    credit_cap = provenance_penalty + operational_uncertainty_spread
    if knowledge_credit > credit_cap:
        raise ValueError("knowledge_credit exceeds uncertainty credit cap")
    hurdle = base_cost_of_capital + risk_spread + provenance_penalty - knowledge_credit
    floor = base_cost_of_capital + non_diversifiable_risk_floor
    if hurdle < floor:
        raise ValueError("adjusted hurdle rate falls below governed floor")
    return hurdle


def discount_factors(period_rates: Sequence[float]) -> list[float]:
    """Return period-safe discount factors for period-varying hurdle rates."""
    factors: list[float] = []
    accumulator = 1.0
    for rate in period_rates:
        if rate <= -1.0:
            raise ValueError("period rate must be greater than -100%")
        accumulator *= 1.0 / (1.0 + rate)
        factors.append(accumulator)
    return factors


def npv_from_ep(economic_profit_series: Sequence[float], period_rates: Sequence[float]) -> float:
    """Compute additive value from an EP series and period-varying hurdle rates."""
    if len(economic_profit_series) != len(period_rates):
        raise ValueError("economic profit series and rate series must have equal length")
    return sum(ep * df for ep, df in zip(economic_profit_series, discount_factors(period_rates)))


def weighted_inner_product(u: Sequence[float], v: Sequence[float], weights: Sequence[float]) -> float:
    """Compute a non-negative weighted inner product."""
    if not (len(u) == len(v) == len(weights)):
        raise ValueError("vectors and weights must have equal length")
    if any(weight < 0.0 for weight in weights):
        raise ValueError("metric weights must be non-negative")
    return sum(weight * left * right for left, right, weight in zip(u, v, weights))


def cosine_distance(u: Sequence[float], v: Sequence[float], weights: Sequence[float]) -> float:
    """Compute weighted cosine angular distance with floating-point clamping."""
    uu = weighted_inner_product(u, u, weights)
    vv = weighted_inner_product(v, v, weights)
    if uu <= 0.0 or vv <= 0.0:
        raise ValueError("zero-norm vectors are invalid")
    uv = weighted_inner_product(u, v, weights)
    cosine = uv / math.sqrt(uu * vv)
    cosine = min(1.0, max(-1.0, cosine))
    return math.acos(cosine)


def weights_sum_to_one(weights: Iterable[float]) -> bool:
    """Return whether a finite weight vector is normalized to one."""
    values = list(weights)
    return bool(values) and all(value >= 0.0 for value in values) and math.isclose(
        reduce(lambda acc, item: acc + item, values, 0.0),
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def reconcile_ep_components(components: Mapping[str, float]) -> float:
    """Reconcile canonical EP components to economic profit.

    Positive components increase EP; negative components consume EP. This mirrors
    the current product specification and creates a single reusable invariant for
    fixtures and schema-backed outputs.
    """
    required = {
        "revenue",
        "expected_loss",
        "expense",
        "funding_costs",
        "funding_credits",
        "taxes",
        "capital_charge",
    }
    missing = required - set(components)
    if missing:
        raise ValueError(f"missing EP components: {sorted(missing)}")
    return (
        components["revenue"]
        - components["expected_loss"]
        - components["expense"]
        - components["funding_costs"]
        + components["funding_credits"]
        - components["taxes"]
        - components["capital_charge"]
    )
