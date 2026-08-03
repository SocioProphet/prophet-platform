"""Basel IRB-Advanced regulatory capital, AMA operational risk, and the reg-vs-economic comparison.

The estate needs to state, quantitatively, *both* numbers for any exposure — the regulator's and the
bank's own — and show where they diverge. This module implements:

1. **IRB-Advanced credit-risk capital** — the genuine Basel corporate risk-weight function: the
   Vasicek 99.9% conditional loss with the supervisory asset-correlation R(PD) and maturity
   adjustment b(PD). K is the *unexpected*-loss capital (EL is subtracted, since EL is covered by
   provisions), RWA = K·12.5·EAD, and regulatory capital = 8%·RWA.

2. **AMA operational risk** — a loss-distribution-approach (LDA) op-risk model: Poisson frequency ×
   lognormal severity per Basel event type, aggregated by Monte-Carlo to the 99.9% one-year VaR.

3. **Economic vs regulatory** — economic capital from the bank's *own* confidence and its
   cross-risk diversification, side by side with the regulatory floor, with the divergence made
   explicit (economic can sit above OR below the floor).

Stdlib only (``statistics.NormalDist`` + ``random``).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()
_G = _N.inv_cdf            # inverse standard normal
_PHI = _N.cdf             # standard normal cdf
_Q_REG = 0.999            # Basel confidence


# --------------------------------------------------------------------------- #
# 1. IRB-Advanced credit-risk regulatory capital (corporate)                  #
# --------------------------------------------------------------------------- #

def irb_correlation(pd: float) -> float:
    """Supervisory asset correlation R(PD) for corporate exposures — decreases from 0.24 to 0.12
    as PD rises (idiosyncratic risk dominates for weaker names)."""
    w = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    return 0.12 * w + 0.24 * (1 - w)


def irb_maturity_adjustment(pd: float) -> float:
    """Maturity-adjustment slope b(PD)."""
    return (0.11852 - 0.05478 * math.log(pd)) ** 2


def irb_capital_requirement(pd: float, lgd: float, maturity: float = 2.5) -> float:
    """Per-unit-EAD capital requirement K (unexpected loss), the core Basel IRB corporate formula."""
    pd = min(max(pd, 1e-6), 0.9999)
    R = irb_correlation(pd)
    b = irb_maturity_adjustment(pd)
    conditional = _PHI(((1 - R) ** -0.5) * _G(pd) + ((R / (1 - R)) ** 0.5) * _G(_Q_REG))
    k = (lgd * conditional - pd * lgd) * (1.0 / (1 - 1.5 * b)) * (1 + (maturity - 2.5) * b)
    return max(0.0, k)


def irb_regulatory_capital(pd: float, lgd: float, ead: float, maturity: float = 2.5) -> dict:
    """Full IRB readout for an exposure: K, RWA, 8% regulatory capital, and expected loss."""
    k = irb_capital_requirement(pd, lgd, maturity)
    rwa = k * 12.5 * ead
    return {
        "pd": pd, "lgd": lgd, "ead": ead, "maturity": maturity,
        "correlation_R": round(irb_correlation(pd), 5),
        "capital_requirement_K": round(k, 6),
        "rwa": round(rwa, 4),
        "regulatory_capital": round(0.08 * rwa, 4),   # = k * ead
        "expected_loss": round(pd * lgd * ead, 4),
        "approach": "IRB-Advanced (corporate)",
    }


# --------------------------------------------------------------------------- #
# 2. AMA operational risk (loss-distribution approach)                        #
# --------------------------------------------------------------------------- #

# The seven Basel operational-risk event types.
OPRISK_EVENT_TYPES = [
    "internal_fraud", "external_fraud", "employment_practices",
    "clients_products_business", "damage_physical_assets",
    "business_disruption", "execution_delivery",
]


@dataclass(frozen=True)
class OpRiskCell:
    """Frequency/severity of one event type. `annual_frequency` = Poisson λ; severity is lognormal
    with (mu, sigma) on log($m)."""
    event_type: str
    annual_frequency: float
    severity_mu: float
    severity_sigma: float


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def oprisk_ama_capital(cells, sims: int = 30000, seed: int = 7, confidence: float = _Q_REG) -> dict:
    """LDA op-risk: aggregate Poisson×lognormal losses over `sims` years, return the 99.9% VaR and the
    op-risk capital (VaR − expected annual loss)."""
    rng = random.Random(seed)
    losses = []
    for _ in range(sims):
        yr = 0.0
        for c in cells:
            for _ in range(_poisson(rng, c.annual_frequency)):
                yr += math.exp(c.severity_mu + c.severity_sigma * rng.gauss(0, 1))
        losses.append(yr)
    losses.sort()
    mean = sum(losses) / len(losses)
    var = losses[min(len(losses) - 1, int(confidence * len(losses)))]
    # expected shortfall
    tail = losses[int(confidence * len(losses)):] or [var]
    es = sum(tail) / len(tail)
    return {
        "expected_annual_loss": round(mean, 4),
        "oprisk_var_999": round(var, 4),
        "oprisk_capital": round(var - mean, 4),     # unexpected op-loss
        "oprisk_es_999": round(es, 4),
        "sims": sims, "approach": "AMA (loss-distribution approach)",
    }


# --------------------------------------------------------------------------- #
# 3. Economic vs regulatory capital — quantitative comparison                 #
# --------------------------------------------------------------------------- #

def economic_capital_credit(pd: float, lgd: float, ead: float, rho: float,
                            confidence: float) -> float:
    """The bank's own credit economic capital: Vasicek unexpected loss at its OWN confidence and
    OWN asset correlation (not the supervisory R) — this is what diverges from the IRB floor."""
    wcdr = _PHI((_G(pd) + math.sqrt(rho) * _G(confidence)) / math.sqrt(1 - rho))
    return (wcdr - pd) * lgd * ead


def economic_vs_regulatory(pd: float, lgd: float, ead: float, *, maturity: float = 2.5,
                           own_rho: float = 0.15, own_confidence: float = 0.999,
                           oprisk_cells=None, market_capital: float = 0.0,
                           diversification: float = 0.15) -> dict:
    """Both numbers, side by side, quantitatively.

    Regulatory = IRB credit floor + AMA op-risk + given market capital (additive, no diversification).
    Economic  = own-model credit EC + op-risk + market, LESS a cross-risk diversification benefit.
    """
    reg_credit = irb_regulatory_capital(pd, lgd, ead, maturity)["regulatory_capital"]
    op = oprisk_ama_capital(oprisk_cells, sims=8000) if oprisk_cells else {"oprisk_capital": 0.0}
    reg_op = op["oprisk_capital"]
    reg_total = reg_credit + reg_op + market_capital

    econ_credit = economic_capital_credit(pd, lgd, ead, own_rho, own_confidence)
    econ_standalone = econ_credit + reg_op + market_capital
    econ_total = econ_standalone * (1 - diversification)     # cross-risk diversification benefit

    return {
        "regulatory": {"credit": round(reg_credit, 4), "operational": round(reg_op, 4),
                       "market": round(market_capital, 4), "total": round(reg_total, 4)},
        "economic": {"credit": round(econ_credit, 4), "operational": round(reg_op, 4),
                     "market": round(market_capital, 4), "diversification_benefit_pct": diversification,
                     "total": round(econ_total, 4)},
        "divergence": {
            "economic_minus_regulatory": round(econ_total - reg_total, 4),
            "economic_pct_of_regulatory": round(econ_total / reg_total * 100, 1) if reg_total else None,
            "binding_constraint": "economic" if econ_total > reg_total else "regulatory",
        },
    }
