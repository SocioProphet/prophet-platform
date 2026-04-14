from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_gate_activation_record_matches_test_block_expectations() -> None:
    gate_record = _load("gate_activation_record_0001.json")
    test_block = _load("test_block_0001.json")

    assert set(gate_record["required_gates"]) == set(test_block["expected_gates"])
    assert gate_record["failed_gates"] == []
    assert gate_record["rollback_requirement"] == "required_before_side_effect"


def test_gate_activation_aligns_with_promotion_and_rollback_artifacts() -> None:
    gate_record = _load("gate_activation_record_0001.json")
    promotion = _load("promotion_decision_0001.json")
    rollback = _load("rollback_record_0001.json")

    assert set(gate_record["required_gates"]).issuperset(set(promotion["required_gates"]))
    assert set(rollback["required_gates"]).issubset(set(gate_record["required_gates"]))
    assert gate_record["policy_decision_ref"].startswith("policy://decision/")
    assert gate_record["approval_ref"].startswith("approval://")


def test_gate_activation_is_logical_route_and_tool_write_aligned() -> None:
    gate_record = _load("gate_activation_record_0001.json")
    test_block = _load("test_block_0001.json")

    assert gate_record["action_ref"].endswith("tool_write/logical_route")
    assert test_block["expected_outputs"]["selected_route"] == "logical_route"
    assert test_block["expected_outputs"]["selected_action_profile"] == "tool_write"
