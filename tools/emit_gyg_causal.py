#!/usr/bin/env python3
"""emit_gyg_causal — serve the GYG causal-graph valuation walk the dashboard-bff exposes
at /v1/valuation/causal, including live "what-if" recompute.

DESIGN PRINCIPLE (same as emit_vdt_metrics): the value math is NOT here. The valuation is
computed by the canonical economic-prophet engine (open_ep_framework.vdt.summarize_vdt); the
causal/supply-chain topology comes from the hellgraph seed. This module JOINS the two into one
walkable payload (supply-chain node -> causal edge -> KPI -> driver -> enterprise value) and, for
what-if exploration, applies user assumption overrides to the profile and RE-RUNS THE ENGINE.
We never re-implement the VDT identities here, so recompute cannot fork the value model.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from open_ep_framework.vdt import summarize_vdt
from open_ep_framework.vdt_multiperiod import summarize_vdt_multiperiod

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "apps" / "hellgraph-service" / "seeds" / "gyg-supply-chain-causal.json"
VDT_PATH = ROOT / "apps" / "dashboard-bff" / "data" / "vdt" / "gyg.metrics.json"


def load_seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def load_vdt() -> dict:
    return json.loads(VDT_PATH.read_text(encoding="utf-8"))


def _refresh_graph(seed: dict, summary: dict) -> dict:
    """Refresh the value annotations on the causal graph from a fresh engine summary.
    Topology (nodes, edges, mechanisms) is preserved; only the numbers move."""
    nodes = copy.deepcopy(seed["nodes"])
    edges = copy.deepcopy(seed["edges"])
    kpi_by_name = {k["kpi"]: k["value_contribution"] for k in summary["per_kpi_contribution"]}
    driver_uplift = summary["per_driver_uplift"]

    kpi_name_by_node = {}
    driver_name_by_node = {}
    for n in nodes:
        if "ValueDriverKPI" in n["labels"]:
            name = n["properties"].get("kpi")
            kpi_name_by_node[n["id"]] = name
            n["properties"]["value_contribution"] = kpi_by_name.get(name, 0.0)
        elif "ValueDriver" in n["labels"]:
            name = n["properties"].get("name")
            driver_name_by_node[n["id"]] = name
            n["properties"]["value_uplift"] = driver_uplift.get(name, 0.0)
        elif "Valuation" in n["labels"]:
            n["properties"]["ev_baseline"] = summary["enterprise_value_baseline"]
            n["properties"]["projected_ev"] = summary["projected_enterprise_value"]
            n["properties"]["value_uplift"] = summary["computed_total_value_uplift"]
            n["properties"]["uplift_fraction"] = round(summary["computed_value_uplift_fraction"], 5)

    for e in edges:
        if e["label"] == "CONTRIBUTES_TO":
            e["properties"]["value_contribution"] = kpi_by_name.get(kpi_name_by_node.get(e["from"]), 0.0)
        elif e["label"] == "UPLIFTS":
            e["properties"]["value_uplift"] = driver_uplift.get(driver_name_by_node.get(e["from"]), 0.0)

    return {"nodes": nodes, "edges": edges}


def _timeseries(profile: dict) -> dict:
    """Multi-period projection of the same profile via the canonical multi-period engine."""
    mp = summarize_vdt_multiperiod(profile)
    return {
        "horizon_years": mp["horizon_years"],
        "discount_rate": mp["discount_rate"],
        "periods": [
            {
                "year": p["year"],
                "projected_enterprise_value": p["projected_enterprise_value"],
                "total_value_uplift": p["total_value_uplift"],
                "value_uplift_fraction": round(p["value_uplift_fraction"], 5),
                "incremental_value_uplift": p["incremental_value_uplift"],
            }
            for p in mp["periods"]
        ],
        "terminal_projected_enterprise_value": mp["terminal_projected_enterprise_value"],
        "terminal_total_value_uplift": mp["terminal_total_value_uplift"],
        "present_value_of_uplift": mp["present_value_of_uplift"],
    }


def _compose(summary: dict, profile: dict, seed: dict, vdt_doc: dict, recomputed: bool) -> dict:
    uplift = summary["computed_total_value_uplift"]
    frac = summary["computed_value_uplift_fraction"]
    ev = summary["enterprise_value_baseline"]
    valuation = {
        "currency": "AUD",
        "ev_baseline": ev,
        "projected_ev": summary["projected_enterprise_value"],
        "value_uplift": uplift,
        "uplift_fraction": round(frac, 5),
    }
    return {
        "company": seed["subject"],
        "subject": seed["_provenance"]["subject"],
        "recomputed": recomputed,
        "valuation": valuation,
        "timeseries": _timeseries(profile),
        "causal_graph": _refresh_graph(seed, summary),
        "assumptions_editable": [
            {"kpi": k["kpi"], "driver": k["driver"], "domain": k["domain"],
             "delta_pct": k["delta_pct"], "polarity": k["polarity"]}
            for k in profile["kpis"]
        ],
        "vdt": {
            "scenario": summary["scenario"],
            "industry": summary["industry"],
            "per_driver_uplift": summary["per_driver_uplift"],
            "per_kpi_contribution": summary["per_kpi_contribution"],
            "epistemic_status": profile.get("epistemic_status", {}),
            "assumptions": profile.get("assumptions", []),
            "limitations": profile.get("limitations", []),
            "evidence_refs": profile.get("evidence_refs", []),
        },
        "provenance": {
            "value_source": seed["_provenance"]["value_source"],
            "graph_source": "apps/hellgraph-service/seeds/gyg-supply-chain-causal.json",
            "engine": seed["_provenance"]["engine"],
            "data_provenance": seed["_provenance"]["data_provenance"],
            "vdt": vdt_doc.get("_provenance", {}),
        },
        "headline": (
            f"{seed['_provenance']['subject']}: the supply-chain causal graph traces "
            f"A${uplift / 1e6:.1f}M ({frac * 100:.2f}%) of enterprise-value uplift onto a "
            f"A${ev / 1e9:.2f}B baseline — advisory measurement from the economic-prophet engine"
            f"{' (recomputed for your assumptions)' if recomputed else ''}, not investment advice."
        ),
    }


def build(company: str = "gyg") -> dict:
    """Default GYG walk from the vendored engine output (no recompute)."""
    seed = load_seed()
    vdt = load_vdt()
    return _compose(vdt["summary"], vdt["profile"], seed, vdt, recomputed=False)


def recompute(overrides: dict, company: str = "gyg") -> dict:
    """Apply user assumption overrides to the GYG profile and RE-RUN the canonical engine.

    overrides = {
      "ev_baseline": <number>,                       # optional
      "kpi_overrides": {"<kpi_name>": <delta_pct>}    # optional per-KPI lever
    }
    """
    seed = load_seed()
    vdt = load_vdt()
    profile = copy.deepcopy(vdt["profile"])

    if overrides.get("ev_baseline") is not None:
        profile["enterprise_value_baseline"] = float(overrides["ev_baseline"])
    if overrides.get("horizon_years") is not None:
        profile["horizon_years"] = int(overrides["horizon_years"])
    if overrides.get("discount_rate") is not None:
        profile["discount_rate"] = float(overrides["discount_rate"])
    kover = overrides.get("kpi_overrides", {}) or {}
    for kpi in profile["kpis"]:
        if kpi["kpi"] in kover and kover[kpi["kpi"]] is not None:
            kpi["delta_pct"] = float(kover[kpi["kpi"]])

    summary = summarize_vdt(profile)  # canonical engine, not re-implemented here
    return _compose(summary, profile, seed, vdt, recomputed=True)


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
