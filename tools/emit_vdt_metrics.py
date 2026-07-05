#!/usr/bin/env python3
"""emit_vdt_metrics — serve the Value Driver Tree view the dashboard-bff exposes at /v1/vdt.

DESIGN PRINCIPLE — the value math is NOT here. `SocioProphet/economic-prophet` is the canonical
economic engine (open_ep_framework.vdt.run_vdt); this module only *serves* an artifact that engine
PRODUCED. We never recompute the EP/UVMC/VDT identities in the BFF (that would fork the value model),
so `build()` reads the vendored engine output and returns it verbatim, provenance intact.

The vendored artifact (apps/dashboard-bff/data/vdt/*.metrics.json) carries the engine's input_hash and
a regen command. To refresh after the engine changes:

    cd ~/dev/economic-prophet && \\
      python -m open_ep_framework.cli --mode vdt --example examples/vdt_software_platforms.json

then re-vendor the {summary, profile} output (see the file's _provenance block).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VDT_DATA_DIR = ROOT / "apps" / "dashboard-bff" / "data" / "vdt"
DEFAULT_ARTIFACT = VDT_DATA_DIR / "vdt_software_platforms.metrics.json"


def load_artifact(path: Path = DEFAULT_ARTIFACT) -> dict:
    """Load one engine-produced VDT artifact ({_provenance, summary, profile})."""
    return json.loads(path.read_text(encoding="utf-8"))


def build(path: Path = DEFAULT_ARTIFACT) -> dict:
    """Shape the engine artifact into the /v1/vdt payload.

    Pulls the tensor (weights/drivers/domains/kpis) from the engine's profile and the computed
    uplifts from the engine's summary. Nothing is recomputed — the numbers are the engine's.
    """
    doc = load_artifact(path)
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
    print(json.dumps(build(), indent=2, sort_keys=True))
