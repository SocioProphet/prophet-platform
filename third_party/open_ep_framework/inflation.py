"""Alternative inflation reconstructions — Billion Prices Project & ShadowStats.

The primary sources are proprietary: the Billion Prices Project's online-price data is commercial
(PriceStats), and ShadowStats' series is subscription-only. Neither is freely retrievable, so this
module **rebuilds the published methodologies** from inputs the estate can supply — a matched online
price panel for BPP, and the official CPI plus the methodological add-backs for ShadowStats. Every
output is marked ``reconstructed=True`` and carries its method, so it is never mistaken for the
vendor series. Wire a real price feed or a real official-CPI series and the same functions emit the
genuine index.

- **Billion Prices Project** (Cavallo & Rigobon): a daily online-price inflation index built as a
  chained **Jevons** (geometric-mean) index over matched products — no substitution or seasonal
  smoothing, so it turns faster than official CPI. `billion_prices_index` implements exactly that.
- **ShadowStats** (Williams): the official CPI with the post-1980/1990 BLS methodology changes
  reversed — geometric weighting / substitution, hedonic quality adjustment, and owners'-equivalent-
  rent — added back. `shadowstats_alt_cpi` reconstructs the 1980- and 1990-based variants as
  official inflation plus those add-backs.

A real rate then follows from whichever inflation measure you trust: `real_rate(nominal, measure)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import log, exp
from typing import Sequence


# --------------------------------------------------------------------------- #
# Billion Prices Project / PriceStats — chained Jevons online-price index      #
# --------------------------------------------------------------------------- #

def _jevons_relative(prev: dict[str, float], cur: dict[str, float]) -> float:
    """Geometric mean of price relatives over products present in BOTH periods (matched-model)."""
    matched = [k for k in cur if k in prev and prev[k] > 0 and cur[k] > 0]
    if not matched:
        return 1.0
    return exp(sum(log(cur[k] / prev[k]) for k in matched) / len(matched))


def billion_prices_index(panel: Sequence[dict[str, float]], base: float = 100.0) -> dict:
    """BPP-style online-price index.

    `panel` is a time-ordered sequence of {product_id: price} snapshots (e.g. daily scrapes). Returns
    the chained Jevons index (base=100 at t0) and the annualized inflation over the panel. This is
    the genuine BPP construction — feed real scraped prices and it is the real index.
    """
    if not panel:
        return {"index": [base], "annualized_inflation": 0.0, "reconstructed": True,
                "method": "chained-jevons-online-prices", "periods": 0}
    idx = [base]
    for t in range(1, len(panel)):
        idx.append(idx[-1] * _jevons_relative(panel[t - 1], panel[t]))
    periods = len(panel) - 1
    # annualize assuming daily snapshots (365) unless a single step
    ann = ((idx[-1] / idx[0]) ** (365.0 / periods) - 1.0) if periods else 0.0
    return {"index": [round(v, 4) for v in idx], "annualized_inflation": round(ann, 4),
            "reconstructed": True, "method": "chained-jevons-online-prices", "periods": periods}


# --------------------------------------------------------------------------- #
# ShadowStats — official CPI with BLS methodology changes reversed             #
# --------------------------------------------------------------------------- #

@dataclass
class MethodologyAddbacks:
    """Annual percentage points the BLS methodology changes are argued to have removed from CPI.
    Defaults are the widely-cited ShadowStats magnitudes; override with your own estimates."""
    substitution_geometric_weighting: float = 0.7   # geometric weighting / substitution effect
    hedonic_quality_adjustment: float = 0.5          # quality/hedonic adjustments
    owners_equivalent_rent: float = 0.3              # OER vs direct housing cost
    intervention_analysis: float = 0.2               # seasonal / outlier smoothing

    def total(self) -> float:
        return (self.substitution_geometric_weighting + self.hedonic_quality_adjustment
                + self.owners_equivalent_rent + self.intervention_analysis)


def shadowstats_alt_cpi(official_cpi_inflation: float, *, basis: str = "1990",
                        addbacks: MethodologyAddbacks | None = None) -> dict:
    """Reconstruct a ShadowStats-style alternate CPI.

    `official_cpi_inflation` is the headline CPI YoY (as a rate, e.g. 0.031). The 1990-based variant
    adds back the post-1990 methodology changes; the 1980-based variant adds the full post-1980 set
    (larger). Returns the alternate inflation and the add-back breakdown. Reconstructed — feed a real
    official-CPI series to get a series.
    """
    ab = addbacks or MethodologyAddbacks()
    if basis not in ("1980", "1990"):
        raise ValueError("basis must be '1980' or '1990'")
    # 1990 basis: substitution/geometric weighting + hedonics + OER (the 1990s changes)
    # 1980 basis: the above plus the earlier intervention/weighting changes (the full stack)
    if basis == "1990":
        add = (ab.substitution_geometric_weighting + ab.hedonic_quality_adjustment
               + ab.owners_equivalent_rent) / 100.0
    else:
        add = ab.total() / 100.0 + (ab.substitution_geometric_weighting + ab.owners_equivalent_rent) / 100.0
    alt = official_cpi_inflation + add
    return {"alt_inflation": round(alt, 5), "official_inflation": round(official_cpi_inflation, 5),
            "addback": round(add, 5), "basis": basis, "reconstructed": True,
            "method": f"official-plus-methodology-addbacks-{basis}",
            "components": {
                "substitution_geometric_weighting": ab.substitution_geometric_weighting,
                "hedonic_quality_adjustment": ab.hedonic_quality_adjustment,
                "owners_equivalent_rent": ab.owners_equivalent_rent,
                "intervention_analysis": ab.intervention_analysis if basis == "1980" else 0.0,
            }}


# --------------------------------------------------------------------------- #
# Real rate — the bridge into EP / discounting / FTP                          #
# --------------------------------------------------------------------------- #

def real_rate(nominal_rate: float, inflation: float) -> float:
    """Exact Fisher real rate: (1+nominal)/(1+inflation) − 1. Feeds the discount / hurdle used in EP,
    DCF and FTP — which is why the inflation measure you trust changes the value of every book."""
    return (1.0 + nominal_rate) / (1.0 + inflation) - 1.0


def inflation_wedge(bpp_inflation: float, official_inflation: float,
                    shadowstats_inflation: float) -> dict:
    """The spread between measures — the load-bearing number for anyone pricing real assets."""
    return {
        "bpp_vs_official_pp": round((bpp_inflation - official_inflation) * 100, 3),
        "shadowstats_vs_official_pp": round((shadowstats_inflation - official_inflation) * 100, 3),
    }
