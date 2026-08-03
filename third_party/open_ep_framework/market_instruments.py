"""Options, volatility surface, Merton bridge and the Ross recovery seam (MKT-1).

This layer turns option prices into a risk-neutral implied distribution ``F_Q`` that
the risk kernel (``risk_measures``) can score, bridges structural credit to equity
options (Merton), and exposes a documented risk-neutral -> physical transform (Ross /
Arrow-Debreu). It consumes ``risk_measures`` (F objects), ``term_calculus`` (the
second-derivative operator for Breeden-Litzenberger) and ``expected_loss`` (EL identity).

Chain: VolSurface -> (Breeden-Litzenberger) F_Q -> (Ross/Radon-Nikodym) physical F ->
LPM / Sortino / ES downside measures.

Teeth:
  * a put-skew surface implies a fatter downside than a flat-vol lognormal;
  * a surface with negative implied variance or a static-arbitrage violation
    (calendar / butterfly) is REJECTED;
  * Merton: equity = call on assets, risky debt = risk-free - put (put-call parity),
    and PD & recovery move inversely with leverage; EL reconciles via PD*LGD*EAD;
  * the Ross transform with an identity kernel returns F_Q unchanged.

Deterministic, stdlib only (Black-76 via math.erf).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .expected_loss import expected_loss_amount
from .domain import ExpectedLossInputs
from .risk_measures import LossDistribution
from .term_calculus import second_difference


class MarketInstrumentError(ValueError):
    """Raised for an arbitrageable surface or an invalid instrument (REJECTED)."""


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# Black-76 forward option pricing
# --------------------------------------------------------------------------- #
def bs_call(forward: float, strike: float, vol: float, t: float, df: float = 1.0) -> float:
    """Black-76 forward call price."""
    if vol <= 0 or t <= 0:
        return df * max(forward - strike, 0.0)
    v = vol * math.sqrt(t)
    d1 = (math.log(forward / strike) + 0.5 * vol * vol * t) / v
    d2 = d1 - v
    return df * (forward * _norm_cdf(d1) - strike * _norm_cdf(d2))


def bs_put(forward: float, strike: float, vol: float, t: float, df: float = 1.0) -> float:
    """Black-76 forward put price (put-call parity)."""
    return bs_call(forward, strike, vol, t, df) - df * (forward - strike)


# --------------------------------------------------------------------------- #
# volatility surface
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VolSurface:
    """Implied vol by (tenor, strike). ``nodes`` = tuple of (tenor, strike, vol)."""

    nodes: tuple[tuple[float, float, float], ...]

    @classmethod
    def from_nodes(cls, nodes) -> "VolSurface":
        return cls(tuple((float(n["tenor"]), float(n["strike"]), float(n["vol"])) for n in nodes))

    def tenors(self) -> list[float]:
        return sorted({t for t, _, _ in self.nodes})

    def strikes(self, tenor: float) -> list[float]:
        return sorted(s for t, s, _ in self.nodes if abs(t - tenor) < 1e-12)

    def implied_vol(self, tenor: float, strike: float) -> float:
        """Implied vol at (tenor, strike): linear in strike within the tenor slice."""
        slice_ = sorted((s, v) for t, s, v in self.nodes if abs(t - tenor) < 1e-12)
        if not slice_:
            raise MarketInstrumentError(f"no surface slice at tenor {tenor}")
        if strike <= slice_[0][0]:
            return slice_[0][1]
        if strike >= slice_[-1][0]:
            return slice_[-1][1]
        for (s0, v0), (s1, v1) in zip(slice_, slice_[1:]):
            if s0 <= strike <= s1:
                return v0 + (strike - s0) / (s1 - s0) * (v1 - v0)
        return slice_[-1][1]

    def validate(self, forward: float = 1.0) -> bool:
        """Reject negative implied variance and static-arbitrage violations.

        * negative/zero vol -> negative or zero implied variance -> REJECTED;
        * calendar arbitrage: total variance vol^2 * T must be non-decreasing in T
          for the same strike -> REJECTED if it falls;
        * butterfly arbitrage: call price must be convex in strike (density >= 0) ->
          REJECTED if a negative butterfly (concavity) appears.
        """
        for t, s, v in self.nodes:
            if v <= 0 or v * v * t <= 0:
                raise MarketInstrumentError(
                    f"REJECTED: non-positive implied variance at (tenor={t}, strike={s})"
                )
        # calendar
        strikes_by = {}
        for t, s, v in self.nodes:
            strikes_by.setdefault(s, []).append((t, v))
        for s, tv in strikes_by.items():
            tv.sort()
            for (t0, v0), (t1, v1) in zip(tv, tv[1:]):
                if v1 * v1 * t1 + 1e-12 < v0 * v0 * t0:
                    raise MarketInstrumentError(
                        f"REJECTED: calendar arbitrage at strike {s}: total variance falls "
                        f"from tenor {t0} to {t1}"
                    )
        # butterfly (convexity of call in strike on each tenor slice)
        for t in self.tenors():
            ks = self.strikes(t)
            if len(ks) >= 3:
                calls = [bs_call(forward, k, self.implied_vol(t, k), t) for k in ks]
                for i in range(1, len(ks) - 1):
                    left = (calls[i] - calls[i - 1]) / (ks[i] - ks[i - 1])
                    right = (calls[i + 1] - calls[i]) / (ks[i + 1] - ks[i])
                    # C(K) must be convex (density = C'' >= 0), i.e. slope non-decreasing.
                    if left - right > 1e-9:
                        raise MarketInstrumentError(
                            f"REJECTED: butterfly arbitrage at tenor {t} near strike {ks[i]}"
                        )
        return True


def implied_distribution(surface: VolSurface, tenor: float, forward: float,
                         n_samples: int = 500, width: float = 0.8) -> LossDistribution:
    """Breeden-Litzenberger risk-neutral implied distribution F_Q from the surface.

    The risk-neutral density is q(K) = d2C/dK2; F_Q is returned as return samples
    (K/forward - 1) drawn by inverse-transform from that density. Feeds the downside
    measures in ``risk_measures``.
    """
    surface.validate(forward)
    lo = forward * (1.0 - width)
    hi = forward * (1.0 + width)
    grid_n = 200
    step = (hi - lo) / grid_n
    strikes = [lo + i * step for i in range(1, grid_n)]

    def call_fn(k: float) -> float:
        return bs_call(forward, k, surface.implied_vol(tenor, k), tenor)

    densities = []
    for k in strikes:
        q = second_difference(call_fn, k, step)
        densities.append(max(q, 0.0))
    mass = sum(densities)
    if mass <= 0:
        raise MarketInstrumentError("implied density has non-positive mass")
    probs = [d / mass for d in densities]

    # inverse-transform sample deterministically on the quantile grid
    cdf = []
    acc = 0.0
    for p in probs:
        acc += p
        cdf.append(acc)
    samples = []
    for i in range(n_samples):
        u = (i + 0.5) / n_samples
        j = 0
        while j < len(cdf) - 1 and cdf[j] < u:
            j += 1
        samples.append(strikes[j] / forward - 1.0)
    return LossDistribution.from_samples(samples)


# --------------------------------------------------------------------------- #
# Merton structural bridge
# --------------------------------------------------------------------------- #
def equity_as_call(asset_value: float, debt: float, asset_vol: float, t: float,
                   r: float = 0.0, ead: float | None = None) -> dict:
    """Merton bridge: equity = call on assets (strike = debt); risky debt = rf - put.

    Returns equity, put, risky/riskfree debt, PD = N(-d2), recovery (endogenous) and
    LGD = 1 - recovery. PD and recovery move inversely with leverage. EL reconciles via
    the estate expected-loss identity PD*LGD*EAD (default EAD = discounted debt).
    """
    if asset_vol <= 0 or t <= 0:
        raise MarketInstrumentError("asset_vol and t must be positive")
    v = asset_vol * math.sqrt(t)
    d1 = (math.log(asset_value / debt) + (r + 0.5 * asset_vol * asset_vol) * t) / v
    d2 = d1 - v
    rf_debt = debt * math.exp(-r * t)
    equity = asset_value * _norm_cdf(d1) - rf_debt * _norm_cdf(d2)
    put = rf_debt * _norm_cdf(-d2) - asset_value * _norm_cdf(-d1)
    risky_debt = asset_value - equity  # == rf_debt - put
    pd = _norm_cdf(-d2)
    denom = rf_debt * _norm_cdf(-d2)
    recovery = min(1.0, (asset_value * _norm_cdf(-d1)) / denom) if denom > 0 else 0.0
    lgd = 1.0 - recovery
    ead_used = ead if ead is not None else rf_debt
    el = expected_loss_amount(ExpectedLossInputs(pd=pd, lgd=lgd, ead=ead_used))
    return {
        "equity": equity,
        "put": put,
        "risky_debt": risky_debt,
        "riskfree_debt": rf_debt,
        "pd": pd,
        "recovery": recovery,
        "lgd": lgd,
        "ead": ead_used,
        "expected_loss": el,
        "d1": d1,
        "d2": d2,
    }


def pd_from_structural(asset_value: float, debt: float, asset_vol: float, t: float,
                       r: float = 0.0) -> float:
    """Merton PD = N(-d2)."""
    return equity_as_call(asset_value, debt, asset_vol, t, r)["pd"]


# --------------------------------------------------------------------------- #
# Ross recovery / Arrow-Debreu seam: risk-neutral -> physical
# --------------------------------------------------------------------------- #
def physical_from_riskneutral(f_q: LossDistribution, kernel_fn=None,
                              n_samples: int | None = None) -> LossDistribution:
    """Map a risk-neutral F_Q to a physical F via a pricing-kernel (Ross seam).

    ``kernel_fn(return)`` is the pricing kernel m(state); the Radon-Nikodym derivative
    dP/dQ is proportional to 1/m. With ``kernel_fn=None`` the transform is the identity
    and returns F_Q UNCHANGED (the documented tooth). A risk-averse kernel (larger m in
    bad states) up-weights good states under P, so the physical mean exceeds the
    risk-neutral mean (the equity premium). This is the transparent, testable seam where
    a full Ross recovery (transition-independent kernel) would be plugged in.
    """
    if kernel_fn is None:
        return f_q
    samples = list(f_q.samples)
    weights = []
    for r in samples:
        m = kernel_fn(r)
        if m <= 0:
            raise MarketInstrumentError("pricing kernel must be positive")
        weights.append(1.0 / m)
    total = sum(weights)
    probs = [w / total for w in weights]
    order = sorted(range(len(samples)), key=lambda i: samples[i])
    sorted_samples = [samples[i] for i in order]
    sorted_probs = [probs[i] for i in order]
    cdf = []
    acc = 0.0
    for p in sorted_probs:
        acc += p
        cdf.append(acc)
    n = n_samples or len(samples)
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        j = 0
        while j < len(cdf) - 1 and cdf[j] < u:
            j += 1
        out.append(sorted_samples[j])
    return LossDistribution.from_samples(out)


# --------------------------------------------------------------------------- #
# liquidity premium: volume / regime feeds both curve and surface (light)
# --------------------------------------------------------------------------- #
def liquidity_premium(volume: float, regime_hurst: float = 0.5, base_bps: float = 10.0) -> float:
    """Liquidity premium (bps) as a function of volume and memory regime.

    Falls with traded volume, rises with a persistent (illiquid / trending) regime.
    ``regime_hurst`` is intended to be supplied by the estate memory-regime
    characterizer (injection, not a fork). Feeds both the FTP curve (add to the rate)
    and the vol surface (add to vol). Light reference implementation.
    """
    if volume < 0:
        raise MarketInstrumentError("volume must be non-negative")
    regime_factor = 1.0 + 2.0 * max(0.0, regime_hurst - 0.5)
    return base_bps / (1.0 + volume) * regime_factor
