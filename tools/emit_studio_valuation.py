#!/usr/bin/env python3
"""emit_studio_valuation — Value Driver Studio: a causal valuation for ANY company.

Generalizes the GYG pipeline. Given an exchange:ticker (auto-pull free public financials)
OR manual inputs for a private company, plus an industry value-driver-surface TEMPLATE
(reuses the vendored industry VDT tensors), it:
  1. sets the enterprise-value baseline from the real/entered EV,
  2. runs the CANONICAL economic-prophet engine on the template's driver x domain tensor,
  3. builds a causal graph (KPI -> driver -> enterprise value),
and returns the SAME payload shape the client-vue causal-valuation surface already renders.
The value math is never re-implemented here. Provenance is stamped; advisory only.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VDT_DIR = ROOT / "apps" / "dashboard-bff" / "data" / "vdt"

# Templates the Studio offers = the vendored industry VDT surfaces (drivers x domains x weights).
TEMPLATES = ["software", "banks", "energy", "realestate", "materials", "consumerstaples", "gyg"]
DEFAULT_TEMPLATE = "software"


def templates() -> list[dict]:
    out = []
    for t in TEMPLATES:
        p = VDT_DIR / f"{t}.metrics.json"
        if p.exists():
            prof = json.loads(p.read_text(encoding="utf-8")).get("profile", {})
            out.append({"id": t, "industry": prof.get("industry", t)})
    return out


def _load_template_profile(tid: str) -> dict:
    p = VDT_DIR / f"{tid}.metrics.json"
    if not p.exists():
        p = VDT_DIR / f"{DEFAULT_TEMPLATE}.metrics.json"
    return copy.deepcopy(json.loads(p.read_text(encoding="utf-8"))["profile"])


def _generic_graph(summary: dict, subject: str, currency: str) -> dict:
    """Company-agnostic causal graph: value-driver KPI -> driver -> enterprise value.
    (No physical supply-chain layer — that stays specific to modeled subjects like GYG.)"""
    nodes = [{
        "id": "co:valuation", "labels": ["Valuation"],
        "properties": {"name": f"{subject} enterprise value", "currency": currency,
                       "ev_baseline": summary["enterprise_value_baseline"],
                       "projected_ev": summary["projected_enterprise_value"],
                       "value_uplift": summary["computed_total_value_uplift"],
                       "uplift_fraction": round(summary["computed_value_uplift_fraction"], 5)}}]
    edges = []
    for driver, uplift in summary["per_driver_uplift"].items():
        nodes.append({"id": f"co:driver:{driver}", "labels": ["ValueDriver"],
                      "properties": {"name": driver, "value_uplift": uplift}})
        edges.append({"label": "UPLIFTS", "from": f"co:driver:{driver}", "to": "co:valuation",
                      "properties": {"value_uplift": uplift}})
    for k in summary["per_kpi_contribution"]:
        nid = f"co:kpi:{k['kpi']}"
        nodes.append({"id": nid, "labels": ["ValueDriverKPI"],
                      "properties": {"name": k["kpi"], "kpi": k["kpi"], "driver": k["driver"],
                                     "value_contribution": k["value_contribution"]}})
        edges.append({"label": "CONTRIBUTES_TO", "from": nid, "to": f"co:driver:{k['driver']}",
                      "properties": {"value_contribution": k["value_contribution"]}})
    return {"nodes": nodes, "edges": edges}


def _timeseries(profile: dict) -> dict:
    try:
        from open_ep_framework.vdt_multiperiod import summarize_vdt_multiperiod
    except ImportError:
        ev = profile.get("enterprise_value_baseline", 0.0)
        return {"horizon_years": 1, "discount_rate": 0.0, "periods": [],
                "terminal_projected_enterprise_value": ev, "terminal_total_value_uplift": 0.0,
                "present_value_of_uplift": 0.0, "engine_unavailable": True}
    mp = summarize_vdt_multiperiod(profile)
    return {"horizon_years": mp["horizon_years"], "discount_rate": mp["discount_rate"],
            "periods": [{"year": p["year"], "projected_enterprise_value": p["projected_enterprise_value"],
                         "total_value_uplift": p["total_value_uplift"],
                         "value_uplift_fraction": round(p["value_uplift_fraction"], 5),
                         "incremental_value_uplift": p["incremental_value_uplift"]} for p in mp["periods"]],
            "terminal_projected_enterprise_value": mp["terminal_projected_enterprise_value"],
            "terminal_total_value_uplift": mp["terminal_total_value_uplift"],
            "present_value_of_uplift": mp["present_value_of_uplift"]}


def build_valuation(ticker: str | None = None, template: str = DEFAULT_TEMPLATE,
                    ev_baseline: float | None = None, name: str | None = None,
                    horizon_years: int = 5, discount_rate: float = 0.09,
                    kpi_overrides: dict | None = None) -> dict:
    currency = "USD"
    financials = None
    if ticker:
        from importlib import util as _u
        spec = _u.spec_from_file_location("emit_company_financials", ROOT / "tools" / "emit_company_financials.py")
        mod = _u.module_from_spec(spec); spec.loader.exec_module(mod)  # type: ignore
        financials = mod.fetch(ticker)
        if financials.get("available"):
            ev_baseline = financials.get("enterprise_value") or financials.get("market_cap") or ev_baseline
            name = financials.get("name") or name
            currency = financials.get("currency") or currency

    profile = _load_template_profile(template)
    subject = name or ticker or "Private company"
    profile["scenario"] = f"studio:{subject}"
    if ev_baseline:
        profile["enterprise_value_baseline"] = float(ev_baseline)
    profile["horizon_years"] = int(horizon_years)
    profile["discount_rate"] = float(discount_rate)
    for kpi in profile.get("kpis", []):
        if kpi_overrides and kpi["kpi"] in kpi_overrides and kpi_overrides[kpi["kpi"]] is not None:
            kpi["delta_pct"] = float(kpi_overrides[kpi["kpi"]])

    from open_ep_framework.vdt import summarize_vdt  # canonical engine, lazy
    summary = summarize_vdt(profile)
    ev = summary["enterprise_value_baseline"]
    uplift = summary["computed_total_value_uplift"]
    frac = summary["computed_value_uplift_fraction"]

    return {
        "company": (ticker or subject),
        "subject": subject,
        "ticker": ticker,
        "template": template,
        "recomputed": bool(kpi_overrides or ticker),
        "valuation": {"currency": currency, "ev_baseline": ev,
                      "projected_ev": summary["projected_enterprise_value"],
                      "value_uplift": uplift, "uplift_fraction": round(frac, 5)},
        "timeseries": _timeseries(profile),
        "causal_graph": _generic_graph(summary, subject, currency),
        "assumptions_editable": [{"kpi": k["kpi"], "driver": k["driver"], "domain": k["domain"],
                                  "delta_pct": k["delta_pct"], "polarity": k["polarity"]}
                                 for k in profile["kpis"]],
        "vdt": {"scenario": profile["scenario"], "industry": summary["industry"],
                "per_driver_uplift": summary["per_driver_uplift"],
                "per_kpi_contribution": summary["per_kpi_contribution"],
                "epistemic_status": {"level": "public_sourced_scenario" if financials and financials.get("available")
                                     else "template_scenario", "review_status": "engine_computed"},
                "assumptions": [f"Enterprise-value baseline from {'public market data ('+ticker+')' if financials and financials.get('available') else 'manual entry'}.",
                                f"Value-driver tensor = the '{template}' industry template (analyst attribution).",
                                "KPI deltas are a scenario; adjust them to explore. Advisory only — not investment advice."],
                "limitations": ["Template scenario, not company-specific segment economics.",
                                "No securities, investment, or valuation-opinion conclusion is implied."],
                "evidence_refs": (financials.get("provenance", {}).get("source", "") if financials else "manual entry",)},
        "provenance": {"engine": "open_ep_framework.vdt.summarize_vdt",
                       "data_provenance": "public_market_data" if financials and financials.get("available") else "manual",
                       "financials": financials or {"available": False, "note": "manual / private company"}},
        "headline": (f"{subject}: the '{template}' value-driver scenario projects "
                     f"{currency} {uplift/1e6:.1f}M ({frac*100:.2f}%) enterprise-value uplift on a "
                     f"{currency} {ev/1e9:.2f}B baseline — advisory measurement from the economic-prophet "
                     f"engine, not investment advice."),
    }


if __name__ == "__main__":
    import sys
    tk = sys.argv[1] if len(sys.argv) > 1 else "GYG.AX"
    tpl = sys.argv[2] if len(sys.argv) > 2 else "consumerstaples"
    print(json.dumps(build_valuation(ticker=tk, template=tpl), indent=2))
