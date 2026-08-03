"""Producer: governed portfolio risk / capital / inflation / marketing facts.

Feeds the dashboard-bff `/v1/risk/portfolio-facts` endpoint. **Dogfood:** every number is computed by
the estate's own governed library — the vendored `open_ep_framework` (third_party/, single source of
truth with economic-prophet), not hand-mirrored formulas. Risk/EP/capital/marketing facts are
`reproduced_by_us` (our model); the alternative-inflation facts are `reconstructed` (vendor series
proprietary), flagged so the UI badges provenance honestly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "third_party"))          # dogfood: run our own governed package

from open_ep_framework import (                          # noqa: E402  (the vendored framework)
    expected_loss as _el, recovery as _rec, inflation as _inf,
    regulatory_capital as _rc, conversion_infotheory as _cvt,
)
from open_ep_framework.domain import ExpectedLossInputs, RecoverySurfaceInputs  # noqa: E402

_FIXTURE = _ROOT / "apps" / "dashboard-bff" / "data" / "risk_ep_portfolio.json"
HURDLE = 0.12


def _load() -> dict:
    return json.loads(_FIXTURE.read_text()) if _FIXTURE.exists() else {}


def _fact(name, value, unit, trust="reproduced", reconstructed=False):
    return {"name": name, "value": round(float(value), 6), "unit": unit,
            "source_trust_class": "RECONSTRUCTED" if reconstructed else "REPRODUCED",
            "reproduced_by_us": trust == "reproduced", "reconstructed": reconstructed}


def emit(portfolio: dict | None = None) -> dict:
    p = portfolio or _load()
    pd = p.get("pd", 0.02); lgd = p.get("lgd", 0.45); ead = p.get("ead", 100.0)
    maturity = p.get("maturity", 2.5); own_rho = p.get("rho", 0.15)
    conf = p.get("confidence", 0.999)

    # --- credit: EL + Basel IRB-Advanced regulatory capital (real funcs) ---
    el = _el.expected_loss_amount(ExpectedLossInputs(pd, lgd, ead))
    irb = _rc.irb_regulatory_capital(pd, lgd, ead, maturity)

    # --- operational risk (AMA / LDA) ---
    cells_cfg = p.get("oprisk_cells") or [
        {"event_type": t, "annual_frequency": 2.0, "severity_mu": 0.0, "severity_sigma": 1.0}
        for t in _rc.OPRISK_EVENT_TYPES]
    cells = [_rc.OpRiskCell(**c) for c in cells_cfg]

    # --- reg vs economic (both, quantitatively) ---
    reg_econ = _rc.economic_vs_regulatory(
        pd, lgd, ead, maturity=maturity, own_rho=own_rho, own_confidence=conf,
        oprisk_cells=cells, market_capital=p.get("market_capital", 5.0),
        diversification=p.get("diversification", 0.15))

    # --- recovery surface (Ross / Arrow-Debreu) ---
    surf = p.get("recovery_surface", {"seniority": 0.6, "collateral_quality": 0.5,
            "jurisdiction_score": 0.6, "macro_regime": "base", "liquidity_regime": "normal",
            "workout_horizon_days": 540, "market_state_price": 0.5})
    rsi = RecoverySurfaceInputs(**surf)
    rr_p = _rec.planning_recovery(rsi); rr_q = _rec.market_implied_recovery(rsi)
    wedge = _rec.recovery_wedge(rsi)

    # --- inflation (reconstructed) + real rate ---
    off = p.get("official_cpi", 0.031); nominal = p.get("nominal_rate", 0.055)
    panel = p.get("online_price_panel") or []
    bpp = _inf.billion_prices_index(panel)["annualized_inflation"] if panel else off + 0.006
    ss = _inf.shadowstats_alt_cpi(off, basis=p.get("shadowstats_basis", "1990"))["alt_inflation"]

    # --- marketing / conversion (information-theoretic) for our own companies ---
    companies = p.get("companies", [])
    marketing = []
    for co in companies:
        ch = {k: _cvt.ChannelStats(**v) for k, v in co["channels"].items()}
        eff = _cvt.marketing_efficiency(ch, co["spend"], ltv=co.get("ltv", 400.0),
                                        monthly_margin=co.get("monthly_margin", 30.0))
        marketing.append({"company": co["name"], **eff})

    facts = [
        _fact("expected_loss", el, "usd_m"),
        _fact("pd", pd, "ratio"), _fact("lgd", lgd, "ratio"), _fact("ead", ead, "usd_m"),
        _fact("irb_correlation", irb["correlation_R"], "ratio"),
        _fact("irb_rwa", irb["rwa"], "usd_m"),
        _fact("regulatory_capital_credit", irb["regulatory_capital"], "usd_m"),
        _fact("oprisk_capital_ama", reg_econ["regulatory"]["operational"], "usd_m"),
        _fact("regulatory_capital_total", reg_econ["regulatory"]["total"], "usd_m"),
        _fact("economic_capital_total", reg_econ["economic"]["total"], "usd_m"),
        _fact("econ_pct_of_regulatory", reg_econ["divergence"]["economic_pct_of_regulatory"] or 0, "pct"),
        _fact("recovery_planning_rr_p", rr_p, "ratio"),
        _fact("recovery_market_rr_q", rr_q, "ratio"),
        _fact("recovery_wedge", wedge, "ratio"),
        _fact("official_cpi_inflation", off, "ratio"),
        _fact("billion_prices_inflation", bpp, "ratio", trust="reconstructed", reconstructed=True),
        _fact("shadowstats_inflation", ss, "ratio", trust="reconstructed", reconstructed=True),
        _fact("real_rate_official", _inf.real_rate(nominal, off), "ratio"),
        _fact("real_rate_shadowstats", _inf.real_rate(nominal, ss), "ratio"),
    ]
    return {
        "service": "dashboard-bff",
        "portfolio_id": p.get("portfolio_id", "illustrative-default"),
        "facts": facts,
        "detail": {"capital_comparison": reg_econ, "marketing": marketing},
        "provenance": {
            "engine": "open_ep_framework (vendored, single source of truth with economic-prophet)",
            "dogfood": True,
            "inflation_source": "reconstructed — Billion Prices Project & ShadowStats proprietary",
            "governed": True,
            "reproduced_fact_count": sum(1 for f in facts if f["reproduced_by_us"]),
            "reconstructed_fact_count": sum(1 for f in facts if f["reconstructed"]),
        },
    }


if __name__ == "__main__":
    print(json.dumps(emit(), indent=2))
