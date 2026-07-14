#!/usr/bin/env python3
"""emit_gyg_locations — serve GYG restaurant locations with a MODELED per-site demographics /
foot-traffic estimate for the map + org digital-twin surface (/v1/locations).

Honesty contract (per the "modeled estimate, clearly labeled" decision):
  - Locations (suburb, state, approx lat/lng, format) are a public-sourced representative sample.
  - est_annual_sales is ANCHORED to GYG's DISCLOSED format average unit volume (drive-thru A$6.7m,
    strip A$5.0m; shopping-centre interpolated) and adjusted by a metro-density tier. It is a model,
    not GYG per-site actuals.
  - modeled_weekly_footfall is DERIVED from est_annual_sales / average ticket — a transparent proxy,
    not measured mobility data.
Every record carries `basis` so the surface can label it. No paid/mobility data is used.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOC_PATH = ROOT / "apps" / "dashboard-bff" / "data" / "gyg" / "locations.json"

# GYG-disclosed format AUV (A$m/yr): drive-thru 6.7, strip 5.0; shopping-centre interpolated.
FORMAT_AUV_AUD = {"drive_thru": 6_700_000.0, "strip": 5_000_000.0, "shopping_centre": 5_500_000.0}
AVG_TICKET_AUD = 18.0  # QSR average transaction, for footfall derivation

# metro-density tier per location id (1 = dense CBD/major metro, 3 = regional). Tier scales AUV.
METRO_TIER = {
    "gyg-qld-queenst": 1, "gyg-qld-fortitude": 1, "gyg-qld-chermside": 2, "gyg-qld-carindale": 2,
    "gyg-qld-indooroopilly": 2, "gyg-qld-southport": 2, "gyg-qld-maroochydore": 3,
    "gyg-nsw-sydcbd": 1, "gyg-nsw-parramatta": 1, "gyg-nsw-bondijunction": 1, "gyg-nsw-liverpool": 2,
    "gyg-nsw-newcastle": 3, "gyg-vic-swanston": 1, "gyg-vic-chadstone": 2, "gyg-vic-geelong": 3,
    "gyg-vic-craigieburn": 2, "gyg-wa-perthcbd": 1, "gyg-wa-haynes": 2, "gyg-act-canberra": 2,
    "gyg-sa-adelaide": 1,
}
TIER_MULT = {1: 1.2, 2: 1.0, 3: 0.8}
TIER_LABEL = {1: "dense CBD / major-metro catchment", 2: "suburban catchment", 3: "regional catchment"}


def _load() -> dict:
    return json.loads(LOC_PATH.read_text(encoding="utf-8"))


def _enrich(loc: dict) -> dict:
    tier = METRO_TIER.get(loc["id"], 2)
    auv = FORMAT_AUV_AUD.get(loc["format"], 5_000_000.0)
    est_annual_sales = round(auv * TIER_MULT[tier])
    weekly_footfall = round(est_annual_sales / AVG_TICKET_AUD / 52.0)
    return {
        **loc,
        "metro_tier": tier,
        "catchment_profile": TIER_LABEL[tier],
        "est_annual_sales_aud": est_annual_sales,
        "modeled_weekly_footfall": weekly_footfall,
        "basis": "modeled: format AUV (GYG-disclosed) x metro tier; footfall = sales / A$18 avg ticket",
    }


def build(company: str = "gyg", q: str = "", state: str = "") -> dict:
    doc = _load()
    locs = [_enrich(l) for l in doc["locations"]]

    ql = q.strip().lower()
    if ql:
        locs = [l for l in locs if ql in l["suburb"].lower() or ql in l["state"].lower() or ql in l["format"].lower()]
    if state:
        locs = [l for l in locs if l["state"].upper() == state.upper()]

    by_state: dict[str, int] = {}
    by_format: dict[str, int] = {}
    sample_sales = 0
    sample_footfall = 0
    for l in locs:
        by_state[l["state"]] = by_state.get(l["state"], 0) + 1
        by_format[l["format"]] = by_format.get(l["format"], 0) + 1
        sample_sales += l["est_annual_sales_aud"]
        sample_footfall += l["modeled_weekly_footfall"]

    totals = doc["_provenance"]["network_totals"]
    return {
        "company": "gyg",
        "subject": doc["_provenance"]["subject"],
        "query": {"q": q, "state": state},
        "locations": locs,
        "sample_size": len(locs),
        "network_totals": totals,
        "org_twin": {
            "sample_modeled_annual_sales_aud": sample_sales,
            "sample_modeled_weekly_footfall": sample_footfall,
            "by_state": by_state,
            "by_format": by_format,
            "network_extrapolation_note": (
                f"Sample of {len(locs)} of {totals['total_au_restaurants']} AU restaurants. "
                f"Modeled sales are anchored to disclosed format AUV; a full-network twin would scale to "
                f"all {totals['total_au_restaurants']} sites."
            ),
        },
        "provenance": doc["_provenance"],
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
