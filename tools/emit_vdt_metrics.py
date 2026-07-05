#!/usr/bin/env python3
"""emit_vdt_metrics — serve the Value Driver Tree views the dashboard-bff exposes at /v1/vdt.

DESIGN PRINCIPLE — the value math is NOT here. `SocioProphet/economic-prophet` is the canonical
economic engine (open_ep_framework.vdt.run_vdt); this module only *serves* artifacts that engine
PRODUCED. We never recompute the EP/UVMC/VDT identities in the BFF (that would fork the value model),
so `build()` reads a vendored engine output and returns it verbatim, provenance intact.

Multiple industries are vendored under apps/dashboard-bff/data/vdt/<id>.metrics.json, indexed by
catalog.json. To refresh after the engine changes, regenerate each from the canonical CLI, e.g.:

    cd ~/dev/economic-prophet && \\
      python -m open_ep_framework.cli --mode vdt --example examples/vdt_software_platforms.json

then re-vendor the {summary, profile} output (see each file's _provenance block).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VDT_DATA_DIR = ROOT / "apps" / "dashboard-bff" / "data" / "vdt"
CATALOG_PATH = VDT_DATA_DIR / "catalog.json"
DEFAULT_INDUSTRY = "software"


def catalog() -> list[dict]:
    """The industries the BFF can serve: [{id, label, industry}, ...]."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["industries"]


def _artifact_path(industry: str) -> Path:
    """Resolve an industry id to its engine-produced artifact, defaulting to software
    when the id is unknown (so the endpoint never 404s on a bad query param)."""
    known = {c["id"] for c in catalog()}
    chosen = industry if industry in known else DEFAULT_INDUSTRY
    return VDT_DATA_DIR / f"{chosen}.metrics.json"


def load_artifact(industry: str = DEFAULT_INDUSTRY) -> dict:
    return json.loads(_artifact_path(industry).read_text(encoding="utf-8"))


def build(industry: str = DEFAULT_INDUSTRY) -> dict:
    """Shape one industry's engine artifact into the /v1/vdt payload. Nothing is recomputed —
    the tensor + uplifts are the engine's; we only reshape and pass provenance through."""
    doc = load_artifact(industry)
    summary = doc["summary"]
    profile = doc["profile"]

    return {
        "industry": summary["industry"],
        "scenario": summary["scenario"],
        "enterprise_value_baseline": summary["enterprise_value_baseline"],
        "drivers": profile["drivers"],
        "domains": profile["domains"],
        "weights": [
            {"driver": w["driver"], "domain": w["domain"], "weight": float(w["weight"])}
            for w in profile["weights"]
        ],
        "per_kpi_contribution": summary["per_kpi_contribution"],
        "per_driver_uplift": summary["per_driver_uplift"],
        "per_domain_uplift": summary["per_domain_uplift"],
        "computed_total_value_uplift": summary["computed_total_value_uplift"],
        "computed_value_uplift_fraction": summary["computed_value_uplift_fraction"],
        "projected_enterprise_value": summary["projected_enterprise_value"],
        "epistemic_status": profile.get("epistemic_status", {}),
        "provenance": doc.get("_provenance", {}),
    }


if __name__ == "__main__":
    print(json.dumps({"catalog": catalog(), "default": build()}, indent=2, sort_keys=True))
