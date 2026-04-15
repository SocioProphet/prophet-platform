from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_graduation_record_matches_agent_and_test_block() -> None:
    graduation = _load("graduation_record_0001.json")
    agent_spec = _load("agent_spec_0001.json")
    test_block = _load("test_block_0001.json")

    assert graduation["agent_ref"] == agent_spec["agent_ref"]
    assert graduation["current_stage"] == agent_spec["graduation"]["current_stage"]
    assert set(graduation["required_gates"]) == set(test_block["expected_gates"])
    assert graduation["target_stage"] == "L4_supervised_actuation"


def test_graduation_has_no_blocking_lanes_for_this_fixture() -> None:
    graduation = _load("graduation_record_0001.json")

    assert graduation["blocking_lanes"] == []
    assert graduation["promotion_window"] == "rolling_30d"
    assert graduation["lane_scores"]["safety_policy"] >= graduation["lane_scores"]["capability"]
    assert graduation["lane_scores"]["provenance_reproducibility"] >= 4


def test_graduation_evidence_refs_link_to_promotion_shape() -> None:
    graduation = _load("graduation_record_0001.json")
    promotion = _load("promotion_decision_0001.json")

    assert "promotion_decision" in graduation["evidence_refs"]
    assert "benchmark_report" in graduation["evidence_refs"]
    assert set(promotion["required_gates"]).issubset(set(graduation["required_gates"]))
