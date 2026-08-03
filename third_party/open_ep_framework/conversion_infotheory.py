"""Information-theoretic conversion & marketing/martech maths.

Conversion attribution is usually done with heuristics (last-touch, first-touch, linear) that have no
theory behind them. This module treats it as an **information** problem: a marketing channel matters
to conversion exactly to the degree that knowing the channel *reduces your uncertainty* about whether
a prospect converts. That reduction is mutual information, and it decomposes additively across
channels — giving a principled, non-linear attribution with no arbitrary weights.

Core quantities (all in bits):
- ``entropy`` — H(Y), the uncertainty in the conversion outcome.
- ``mutual_information`` — I(Channel; Conversion) = H(Y) − H(Y|Channel): how much the channel tells
  you about conversion. Zero iff channel and conversion are independent (a channel that doesn't move
  the needle), maximal when the channel perfectly predicts the outcome.
- ``information_gain_attribution`` — the exact decomposition I(C;Y) = Σ_c P(c)·D_KL(P(Y|c) ‖ P(Y)).
  Each channel's share is how far it pulls the conversion distribution away from the base rate,
  weighted by its traffic. Shares are non-negative and sum to the total mutual information.
- ``kl_divergence`` — the per-channel "lift" in nats/bits: how surprising a channel's conversion
  distribution is versus the base rate.

Marketing/martech economics (CAC, ROAS, LTV:CAC, payback) close the loop from information to money —
because an informative channel is only worth buying if its unit economics clear the hurdle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _log2(x: float) -> float:
    return math.log2(x) if x > 0 else 0.0


def entropy(probs) -> float:
    """Shannon entropy H(p) in bits. Ignores zero-probability outcomes."""
    total = sum(probs)
    if total <= 0:
        return 0.0
    return -sum((p / total) * _log2(p / total) for p in probs if p > 0)


def kl_divergence(p, q) -> float:
    """D_KL(p ‖ q) in bits. p, q are distributions over the same outcomes. +inf-safe (q>0 assumed
    where p>0); returns 0 for identical, always >= 0."""
    sp, sq = sum(p), sum(q)
    out = 0.0
    for pi, qi in zip(p, q):
        if pi <= 0:
            continue
        pn, qn = pi / sp, qi / sq
        if qn <= 0:
            return math.inf
        out += pn * math.log2(pn / qn)
    return max(0.0, out)


@dataclass(frozen=True)
class ChannelStats:
    """Observed counts for one channel over a window."""
    visitors: int
    conversions: int

    @property
    def cr(self) -> float:
        return self.conversions / self.visitors if self.visitors else 0.0


def _base_rate(channels: dict[str, ChannelStats]) -> tuple[float, int]:
    v = sum(c.visitors for c in channels.values())
    k = sum(c.conversions for c in channels.values())
    return (k / v if v else 0.0), v


def mutual_information(channels: dict[str, ChannelStats]) -> float:
    """I(Channel; Conversion) in bits over the joint of (channel, converted?)."""
    base, total_v = _base_rate(channels)
    if total_v == 0:
        return 0.0
    hy = entropy([base, 1 - base])                      # H(Y)
    hy_given_c = 0.0                                     # H(Y | Channel)
    for c in channels.values():
        if c.visitors == 0:
            continue
        hy_given_c += (c.visitors / total_v) * entropy([c.cr, 1 - c.cr])
    return max(0.0, hy - hy_given_c)


def information_gain_attribution(channels: dict[str, ChannelStats]) -> dict:
    """Attribute conversions by information gain: share_c ∝ P(c)·D_KL(P(Y|c) ‖ P(Y)).

    Returns per-channel {info_bits, share, conversion_rate, lift} plus the total mutual information.
    Shares sum to 1 (when I>0); info_bits sum to the mutual information — a genuine decomposition, not
    a heuristic split.
    """
    base, total_v = _base_rate(channels)
    if total_v == 0 or base <= 0 or base >= 1:
        n = len(channels) or 1
        return {"channels": {k: {"info_bits": 0.0, "share": 1.0 / n, "conversion_rate": v.cr,
                                 "lift": 1.0} for k, v in channels.items()},
                "mutual_information_bits": 0.0}
    per = {}
    tot = 0.0
    for name, c in channels.items():
        if c.visitors == 0:
            per[name] = {"info_bits": 0.0, "share": 0.0, "conversion_rate": 0.0, "lift": 0.0}
            continue
        pc = c.visitors / total_v
        info = pc * kl_divergence([c.cr, 1 - c.cr], [base, 1 - base])
        per[name] = {"info_bits": info, "conversion_rate": c.cr, "lift": (c.cr / base) if base else 0.0}
        tot += info
    for name in per:
        per[name]["share"] = (per[name]["info_bits"] / tot) if tot > 0 else 1.0 / len(per)
    return {"channels": per, "mutual_information_bits": tot}


def channel_diversity(spend: dict[str, float]) -> float:
    """Entropy of the spend allocation (bits) — high = diversified, low = concentrated. A drop in
    diversity as you scale one channel is the information signature of diminishing returns."""
    return entropy(list(spend.values()))


# --------------------------------------------------------------------------- #
# Marketing / martech unit economics                                          #
# --------------------------------------------------------------------------- #

def cac(spend: float, conversions: float) -> float:
    """Customer acquisition cost."""
    return spend / conversions if conversions else math.inf


def roas(revenue: float, spend: float) -> float:
    """Return on ad spend."""
    return revenue / spend if spend else 0.0


def ltv_cac_ratio(ltv: float, cac_value: float) -> float:
    return ltv / cac_value if cac_value and math.isfinite(cac_value) else math.inf


def payback_months(cac_value: float, monthly_gross_margin: float) -> float:
    """Months to recover CAC from a customer's monthly gross margin."""
    return cac_value / monthly_gross_margin if monthly_gross_margin else math.inf


def blended_cac(channels: dict[str, ChannelStats], spend: dict[str, float]) -> float:
    total_spend = sum(spend.values())
    total_conv = sum(c.conversions for c in channels.values())
    return cac(total_spend, total_conv)


def marketing_efficiency(channels: dict[str, ChannelStats], spend: dict[str, float],
                         ltv: float, monthly_margin: float) -> dict:
    """One governed readout: per-channel CAC/ROAS/info-share + blended economics. Ties the
    information attribution (which channels *inform* conversion) to the money (which channels *clear*
    the hurdle) — a channel can be informative yet uneconomic, or cheap yet uninformative."""
    attr = information_gain_attribution(channels)
    per = {}
    for name, c in channels.items():
        sp = spend.get(name, 0.0)
        rev = c.conversions * ltv
        per[name] = {
            "cac": cac(sp, c.conversions),
            "roas": roas(rev, sp),
            "conversion_rate": c.cr,
            "info_share": attr["channels"].get(name, {}).get("share", 0.0),
            "lift": attr["channels"].get(name, {}).get("lift", 0.0),
        }
    bc = blended_cac(channels, spend)
    return {
        "channels": per,
        "blended_cac": bc,
        "ltv_cac_ratio": ltv_cac_ratio(ltv, bc),
        "payback_months": payback_months(bc, monthly_margin),
        "mutual_information_bits": attr["mutual_information_bits"],
        "spend_diversity_bits": channel_diversity(spend),
    }
