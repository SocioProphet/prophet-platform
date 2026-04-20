from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_artifact_graph_connects_lifecycle_records() -> None:
    graph = _load("lifecycle_artifact_graph_0001.json")
    promotion = _load("promotion_decision_0001.json")
    rollback = _load("rollback_record_0001.json")
    gate = _load("gate_activation_record_0001.json")
    graduation = _load("graduation_record_0001.json")
    ray_recipe = _load("ray_recipe_lifecycle_0001.json")

    edge_pairs = {(e["from"], e["to"], e["type"]) for e in graph["edges"]}
    assert (ray_recipe["recipe_ref"], promotion["promotion_decision_id"], "promotes") in edge_pairs
    assert (promotion["promotion_decision_id"], gate["gate_activation_record_id"], "requires_gate_activation") in edge_pairs
    assert (gate["gate_activation_record_id"], graduation["graduation_record_id"], "supports_graduation") in edge_pairs
    assert (promotion["promotion_decision_id"], rollback["rollback_record_id"], "rollback_ready") in edge_pairs


def test_artifact_graph_has_expected_evidence_bundle() -> None:
    graph = _load("lifecycle_artifact_graph_0001.json")
    expected = {
        "event_envelope",
        "evidence_receipt",
        "benchmark_report",
        "promotion_decision",
        "rollback_record",
        "gate_activation_record",
        "graduation_record",
    }
    assert set(graph["evidence_refs"]) == expected
