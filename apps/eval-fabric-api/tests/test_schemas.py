from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas" / "eval"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_metric_definition_schema():
    payload = {
        "metric_definition_id": "md_denotation_accuracy",
        "name": "Denotation Accuracy",
        "family": "grounding_factuality",
        "regime": "CWA_BINARY",
        "unit": "ratio",
        "direction": "higher_better",
        "value_type": "scalar",
        "normalizer": "bounded_0_1",
    }
    validate(payload, _schema("metric-definition.schema.json"))


def test_metric_fact_schema():
    payload = {
        "metric_fact_id": "mf_001",
        "ts": "2026-04-09T00:00:00Z",
        "metric_definition_id": "md_denotation_accuracy",
        "source_descriptor_id": "src_internal_eval_runner",
        "provider_id": "our_platform",
        "model_release_id": "model.semantic-stack.2026-04-05",
        "eval_regime": "CWA_BINARY",
        "source_trust_class": "internal_reproduced",
        "freshness_days": 0,
        "reproduced_by_us": True,
        "risk_tier": "high",
        "autonomy_tier": "tool_using_agent",
        "value_scalar": 0.84,
        "sample_n": 200,
        "trial_count": 3,
    }
    validate(payload, _schema("metric-fact.schema.json"))


def test_context_slice_schema():
    payload = {
        "context_slice_id": "ctx_high_assurance_code_agent",
        "length_bucket": "32k_to_128k",
        "modality_mix": ["text", "code"],
        "ontology_depth_bucket": "4_to_6",
        "relation_chain_bucket": "3_to_4",
        "ambiguity_bucket": "2",
        "tool_count_bucket": "3_to_5",
        "freshness_requirement": "live_or_recent",
        "latency_budget": "interactive",
        "cost_budget": "medium",
        "risk_tier": "high",
        "autonomy_tier": "tool_using_agent",
        "domain": "software_engineering",
    }
    validate(payload, _schema("context-slice.schema.json"))


def test_judge_descriptor_schema():
    payload = {
        "judge_descriptor_id": "judge.rule.v1",
        "judge_type": "rule_based",
        "version": "1.0.0",
        "rubric_ref": "rubric://safety/high-assurance/v1",
        "notes": "Deterministic rule gate for policy scenarios.",
    }
    validate(payload, _schema("judge-descriptor.schema.json"))
