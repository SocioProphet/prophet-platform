#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "health-ai" / "demo" / "health-ai-demo-readiness.v0.json"

REQUIRED_BLOCKS = {
    "production_ready",
    "patient_care_action",
    "autonomous_clinical_action",
    "real_clinical_data_processing",
    "customer_facing_healthcare_claim",
    "protected_benchmark_reproduction",
    "ehr_write",
    "clinical_decision_support",
}

REQUIRED_REPOS = {
    "SocioProphet/prophet-core-contracts",
    "SocioProphet/sherlock-search",
    "SocioProphet/sociosphere",
    "SocioProphet/agentplane",
}

def main() -> int:
    try:
        record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERR: failed to load Health-AI demo readiness fixture: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []

    if record.get("schema_version") != "0.1.0":
        errors.append("schema_version must be 0.1.0")
    if record.get("readiness_state") != "ready_for_nonprod_eval":
        errors.append("readiness_state must be ready_for_nonprod_eval")
    for key in (
        "production_ready",
        "patient_care_action",
        "autonomous_clinical_action",
        "real_clinical_data_processing",
        "customer_facing_healthcare_claim",
        "protected_benchmark_reproduction",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")

    blocked = set(record.get("blocked_actions", []))
    missing_blocks = sorted(REQUIRED_BLOCKS - blocked)
    if missing_blocks:
        errors.append(f"missing blocked actions: {missing_blocks}")

    repos = {item.get("repo") for item in record.get("upstream_artifacts", [])}
    missing_repos = sorted(REQUIRED_REPOS - repos)
    if missing_repos:
        errors.append(f"missing upstream repos: {missing_repos}")

    source_classes = {item.get("source_class") for item in record.get("source_basis", [])}
    if "external_competitor_claim" not in source_classes:
        errors.append("missing external_competitor_claim source basis")
    if "benchmark_design_claim" not in source_classes:
        errors.append("missing benchmark_design_claim source basis")

    demo_surface = record.get("demo_surface", {})
    if demo_surface.get("fixture_ready") is not True:
        errors.append("demo_surface.fixture_ready must be true")
    if demo_surface.get("ui_ready") is not False:
        errors.append("demo_surface.ui_ready must be false for this slice")
    if demo_surface.get("api_ready") is not False:
        errors.append("demo_surface.api_ready must be false for this slice")

    blocked_views = set(demo_surface.get("blocked_views", []))
    for blocked_view in (
        "patient_data_entry",
        "clinical_recommendation",
        "diagnosis_or_treatment_advice",
        "production_roi_claim",
        "live_ehr_write",
    ):
        if blocked_view not in blocked_views:
            errors.append(f"missing blocked demo view: {blocked_view}")

    criteria = {item.get("criterion_id"): item.get("status") for item in record.get("eval_readiness_criteria", [])}
    for criterion in (
        "contracts_available",
        "search_packets_available",
        "readiness_registered",
        "control_receipt_available",
    ):
        if criteria.get(criterion) != "satisfied":
            errors.append(f"{criterion} must be satisfied")

    if criteria.get("ui_panel_available") != "pending":
        errors.append("ui_panel_available must remain pending until UI slice lands")

    if record.get("next_allowed_action") != "add_nonprod_ui_panel":
        errors.append("next_allowed_action must be add_nonprod_ui_panel")

    text = FIXTURE.read_text(encoding="utf-8")
    if "healthbench:" in text:
        errors.append("fixture must not reproduce protected HealthBench canary content")

    if errors:
        print("ERR: Health-AI demo readiness validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print("Health-AI demo readiness validates for nonprod eval.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
