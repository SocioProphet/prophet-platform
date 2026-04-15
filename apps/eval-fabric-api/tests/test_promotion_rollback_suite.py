from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_promotion_decision_matches_ray_lifecycle_and_gates() -> None:
    promotion = _load("promotion_decision_0001.json")
    ray_recipe = _load("ray_recipe_lifecycle_0001.json")
    test_block = _load("test_block_0001.json")

    assert promotion["source_ref"] == ray_recipe["recipe_ref"]
    assert promotion["decision"] == "approved_with_gates"
    assert promotion["target_stage"] == "L4_supervised_actuation"
    assert set(promotion["required_gates"]) == set(test_block["expected_gates"])
    assert "benchmark_report" in promotion["evidence_refs"]
    assert "ray_serve_promote" in ray_recipe["lifecycle"]


def test_rollback_record_has_required_gate_and_evidence_shape() -> None:
    rollback = _load("rollback_record_0001.json")
    promotion = _load("promotion_decision_0001.json")

    assert rollback["trigger_ref"] == promotion["promotion_decision_id"]
    assert rollback["status"] == "rollback_ready"
    assert "rollback_gate" in rollback["required_gates"]
    assert "evidence_receipt" in rollback["evidence_refs"]


def test_promotion_and_rollback_share_governed_action_shape() -> None:
    promotion = _load("promotion_decision_0001.json")
    rollback = _load("rollback_record_0001.json")

    common = {"authorization_gate", "scope_gate", "policy_gate", "risk_gate"}
    assert common.issubset(set(promotion["required_gates"]))
    assert common.issubset(set(rollback["required_gates"]))
    assert promotion["subject_ref"].startswith("model://")
    assert rollback["subject_ref"].startswith("service://")
