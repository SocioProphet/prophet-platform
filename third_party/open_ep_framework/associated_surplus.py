from __future__ import annotations

import json
from pathlib import Path

from .validation import validate_json_file


ASSOCIATED_SURPLUS_SCHEMA = "schemas/associated_surplus.schema.json"
REQUIRED_NON_GOALS = {
    "live_money_movement",
    "external_token_issuance",
    "public_chain_settlement",
    "exchange_trading",
    "redemption_rights",
}


def load_associated_surplus_measurement(path: str) -> dict:
    """Load and validate an associated-surplus measurement fixture.

    This runtime is intentionally measurement-only. It validates and summarizes
    doctrine/simulation/audit records; it does not implement money movement,
    token issuance, settlement, redemption, deposit-taking, or payment flows.
    """
    validate_json_file(path, ASSOCIATED_SURPLUS_SCHEMA)
    return json.loads(Path(path).read_text())


def _product(values: list[float]) -> float:
    result = 1.0
    for value in values:
        result *= value
    return result


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def compute_knowledge_quality(knowledge_functional: dict) -> float:
    """Compute K = C * Q * S * P from the Heller knowledge functional."""
    return _product(
        [
            float(knowledge_functional.get("completeness", 0.0)),
            float(knowledge_functional.get("quality", 0.0)),
            float(knowledge_functional.get("stability", 0.0)),
            float(knowledge_functional.get("provenance_strength", 0.0)),
        ]
    )


def compute_gross_associated_surplus(component_scores: dict) -> float:
    """Compute the v0.1 gross associated-surplus scaffold.

    Gross surplus is the product of the bounded quality/leverage terms plus
    explicit network surplus. This is a deterministic measurement scaffold, not
    a universal production function.
    """
    quality_product = _product(
        [
            float(component_scores.get("attention_quality", 0.0)),
            float(component_scores.get("knowledge_quality", 0.0)),
            float(component_scores.get("governance_legitimacy", 0.0)),
            float(component_scores.get("evidence_reliability", 0.0)),
            float(component_scores.get("coordination_bandwidth", 0.0)),
            float(component_scores.get("automation_leverage", 0.0)),
        ]
    )
    return quality_product + float(component_scores.get("network_surplus", 0.0))


def compute_net_associated_surplus(component_scores: dict, deductions: dict) -> float:
    """Compute net associated surplus after extraction/capture/uncertainty/friction."""
    total_deductions = sum(float(value) for value in deductions.values())
    return compute_gross_associated_surplus(component_scores) - total_deductions


def summarize_associated_surplus(data: dict) -> dict:
    """Compute deterministic summary metrics for an associated-surplus run."""
    component_scores = data.get("component_scores", {})
    deductions = data.get("deductions", {})
    knowledge_functional = data.get("knowledge_functional", {})
    triparty_release = data.get("triparty_release", {})
    measurement_boundary = data.get("measurement_boundary", {})
    non_goals = set(measurement_boundary.get("non_goals", []))

    computed_knowledge_quality = compute_knowledge_quality(knowledge_functional)
    computed_gross = compute_gross_associated_surplus(component_scores)
    computed_net = compute_net_associated_surplus(component_scores, deductions)

    lambda_evid = float(triparty_release.get("lambda_evid", 0.0))
    lambda_admit = float(triparty_release.get("lambda_admit", 0.0))
    lambda_release = float(triparty_release.get("lambda_release", 0.0))
    residual = float(triparty_release.get("residual", 0.0))

    return {
        "run_id": data.get("run_id", ""),
        "scenario": data.get("scenario", ""),
        "sphere_count": len(data.get("sphere_refs", [])),
        "community_count": len(data.get("community_refs", [])),
        "knowledge_ref_count": len(data.get("knowledge_refs", [])),
        "governance_ref_count": len(data.get("governance_refs", [])),
        "automation_ref_count": len(data.get("automation_refs", [])),
        "evidence_ref_count": len(data.get("evidence_refs", [])),
        "computed_knowledge_quality": computed_knowledge_quality,
        "reported_knowledge_quality": float(knowledge_functional.get("knowledge_quality", 0.0)),
        "component_knowledge_quality": float(component_scores.get("knowledge_quality", 0.0)),
        "computed_gross_associated_surplus": computed_gross,
        "reported_gross_associated_surplus": float(data.get("gross_associated_surplus", 0.0)),
        "computed_net_associated_surplus": computed_net,
        "reported_net_associated_surplus": float(data.get("net_associated_surplus", 0.0)),
        "total_deductions": sum(float(value) for value in deductions.values()),
        "release_ratio": _safe_ratio(lambda_release, lambda_evid),
        "admission_ratio": _safe_ratio(lambda_admit, lambda_evid),
        "residual_quantity": residual,
        "triparty_state": triparty_release.get("state", ""),
        "measurement_boundary_mode": measurement_boundary.get("mode", ""),
        "required_non_goals_present": sorted(REQUIRED_NON_GOALS & non_goals),
        "missing_required_non_goals": sorted(REQUIRED_NON_GOALS - non_goals),
    }


def run_associated_surplus(path: str) -> dict:
    """Load an associated-surplus measurement run and return summary + record."""
    data = load_associated_surplus_measurement(path)
    return {
        "summary": summarize_associated_surplus(data),
        "measurement": data,
    }
