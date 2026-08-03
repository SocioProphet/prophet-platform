"""Calculus over (value x time) for the risk kernel (TC-1).

The risk kernel is a calculus on two axes:

  * VALUE axis -- risk measures and distributional moments are INTEGRALS over the
    loss/return distribution F (mean, variance, skew, kurtosis, LPM_n, VaR, ES).
    ES is the tail integral consistent with the VaR quantile.
  * TIME axis -- a cash-flow / loss-timing schedule F(t) has time-integral
    functionals: weighted average life (WAL, the first moment of the timing
    distribution) and duration (Macaulay / modified / effective).

Sensitivities are the DERIVATIVES of price w.r.t. a factor:

  * modified duration  = -(1/P) dP/dy
  * convexity          =  (1/P) d2P/dy2
  * generalized Greeks =  numerical dValue/dFactor, d2Value/dFactor2.

Analytic derivatives are reconciled to finite-difference bump-and-reprice
(the teeth), so optionality / prepayment (no closed form) uses the SAME operator
numerically. Marginal / component capital (Euler, in ``risk_measures``) is itself a
numerical derivative of portfolio risk w.r.t. exposure.

Term regime
-----------
The tenor curve has a regime (upward / flat / inverted; persistent vs
mean-reverting). Persistence is read with a Hurst exponent on the tenor
dimension. The estate memory-regime characterizer is the intended source of H;
this module exposes an INJECTION seam (``hurst_fn``) and only falls back to a
local rescaled-range (R/S) estimator when no characterizer is injected, so the
characterizer is consumed rather than forked.

Deterministic / stdlib only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


class TermCalculusError(ValueError):
    pass


@dataclass(frozen=True)
class Cashflow:
    tenor: float  # time in years
    amount: float  # cash flow (or loss) at this tenor


def _flows(schedule) -> list[Cashflow]:
    flows = [c if isinstance(c, Cashflow) else Cashflow(float(c["tenor"]), float(c["amount"]))
             for c in schedule]
    if not flows:
        raise TermCalculusError("cash-flow schedule must be non-empty")
    return flows


# --------------------------------------------------------------------------- #
# time-axis integrals
# --------------------------------------------------------------------------- #
def average_life(schedule) -> float:
    """Weighted average life WAL = sum(t * amount) / sum(amount).

    The first moment of the timing distribution. A bullet (single terminal cash
    flow) has WAL == its maturity.
    """
    flows = _flows(schedule)
    total = sum(f.amount for f in flows)
    if total == 0:
        raise TermCalculusError("WAL undefined for zero total cash flow")
    return sum(f.tenor * f.amount for f in flows) / total


def price(schedule, y: float) -> float:
    """Present value P(y) = sum CF_t / (1+y)^t."""
    if y <= -1.0:
        raise TermCalculusError("yield must exceed -100%")
    return sum(f.amount / (1.0 + y) ** f.tenor for f in _flows(schedule))


def macaulay_duration(schedule, y: float) -> float:
    """Macaulay duration = sum(t * PV_t) / sum(PV_t)."""
    flows = _flows(schedule)
    pvs = [f.amount / (1.0 + y) ** f.tenor for f in flows]
    p = sum(pvs)
    if p == 0:
        raise TermCalculusError("Macaulay duration undefined for zero price")
    return sum(f.tenor * pv for f, pv in zip(flows, pvs)) / p


def modified_duration(schedule, y: float) -> float:
    """Modified duration = Macaulay / (1 + y)."""
    return macaulay_duration(schedule, y) / (1.0 + y)


def analytic_convexity(schedule, y: float) -> float:
    """Analytic convexity = sum(t(t+1) CF_t / (1+y)^(t+2)) / P."""
    flows = _flows(schedule)
    p = price(schedule, y)
    if p == 0:
        raise TermCalculusError("convexity undefined for zero price")
    return sum(f.tenor * (f.tenor + 1.0) * f.amount / (1.0 + y) ** (f.tenor + 2.0)
               for f in flows) / p


# --------------------------------------------------------------------------- #
# calculus operators as first-class (differentiation)
# --------------------------------------------------------------------------- #
def finite_difference(f, x: float, h: float = 1e-5) -> float:
    """Central first derivative f'(x) by bump-and-reprice."""
    return (f(x + h) - f(x - h)) / (2.0 * h)


def second_difference(f, x: float, h: float = 1e-4) -> float:
    """Central second derivative f''(x) by bump-and-reprice."""
    return (f(x + h) + f(x - h) - 2.0 * f(x)) / (h * h)


def effective_duration(reprice, y: float, bump: float = 1e-4) -> float:
    """Effective (numerical) duration -(1/P) dP/dy for arbitrary reprice fns.

    Handles optionality / prepayment where no closed form exists. ``reprice(y)``
    returns price at yield y.
    """
    p0 = reprice(y)
    if p0 == 0:
        raise TermCalculusError("effective duration undefined for zero price")
    return -finite_difference(reprice, y, bump) / p0


def effective_convexity(reprice, y: float, bump: float = 1e-4) -> float:
    """Effective (numerical) convexity (1/P) d2P/dy2."""
    p0 = reprice(y)
    if p0 == 0:
        raise TermCalculusError("effective convexity undefined for zero price")
    return second_difference(reprice, y, bump) / p0


def greek(value_fn, factor: float, order: int = 1, bump: float = 1e-5) -> float:
    """Generalized factor-Greek: order-1 == delta, order-2 == gamma."""
    if order == 1:
        return finite_difference(value_fn, factor, bump)
    if order == 2:
        return second_difference(value_fn, factor, max(bump, 1e-4))
    raise TermCalculusError("greek order must be 1 (delta) or 2 (gamma)")


def taylor_reprice(p0: float, modified_dur: float, convexity: float, dy: float) -> float:
    """2nd-order Taylor reprice: P0 * (1 - Dmod*dy + 0.5*convexity*dy^2)."""
    return p0 * (1.0 - modified_dur * dy + 0.5 * convexity * dy * dy)


# --------------------------------------------------------------------------- #
# term regime: Hurst on the tenor dimension (injectable characterizer)
# --------------------------------------------------------------------------- #
def _rs_hurst(series) -> float:
    """Local rescaled-range (R/S) Hurst estimate; injection fallback only.

    H ~ 0.5 random walk, H > 0.5 persistent, H < 0.5 mean-reverting. This is the
    fallback used only when no estate memory-regime characterizer is injected.
    """
    xs = [float(v) for v in series]
    n = len(xs)
    if n < 4:
        raise TermCalculusError("Hurst estimate needs at least 4 points")
    mean = sum(xs) / n
    dev = 0.0
    cumulative = []
    for x in xs:
        dev += x - mean
        cumulative.append(dev)
    R = max(cumulative) - min(cumulative)
    S = math.sqrt(sum((x - mean) ** 2 for x in xs) / n)
    if S == 0 or R == 0:
        return 0.5
    return math.log(R / S) / math.log(n)


def term_regime(tenor_curve, hurst_fn=None) -> dict:
    """Classify a tenor curve's shape and persistence.

    ``tenor_curve`` is a sequence of (tenor, rate/weight) points sorted by tenor.
    Shape: upward / flat / inverted from the end-to-end slope. Persistence: from a
    Hurst read on the rate dimension. Pass ``hurst_fn`` to bind the estate
    memory-regime characterizer's H; otherwise the local R/S fallback is used.
    """
    points = [(float(t), float(v)) for t, v in tenor_curve]
    if len(points) < 2:
        raise TermCalculusError("term regime needs at least 2 tenor points")
    points.sort(key=lambda p: p[0])
    slope = points[-1][1] - points[0][1]
    if abs(slope) < 1e-9:
        shape = "flat"
    elif slope > 0:
        shape = "upward"
    else:
        shape = "inverted"
    values = [v for _, v in points]
    h_reader = hurst_fn or _rs_hurst
    if hurst_fn is None and len(values) < 4:
        # Not enough tenor points for the R/S fallback; shape still classifies.
        return {
            "shape": shape,
            "slope": slope,
            "hurst": None,
            "persistence": "insufficient_data",
            "hurst_source": "unavailable",
        }
    hurst = h_reader(values)
    if hurst > 0.55:
        persistence = "persistent"
    elif hurst < 0.45:
        persistence = "mean_reverting"
    else:
        persistence = "random_walk"
    return {
        "shape": shape,
        "slope": slope,
        "hurst": hurst,
        "persistence": persistence,
        "hurst_source": "injected" if hurst_fn else "local_rs_fallback",
    }
