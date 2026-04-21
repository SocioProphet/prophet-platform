from __future__ import annotations

import json
from pathlib import Path

from app.lifecycle_artifacts import (
    build_gate_activation_record,
    build_graduation_record,
    build_lifecycle_artifact_graph,
    build_promotion_decision,
    build_rollback_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_build_promotion_decision_matches_fixture() -> None:
    expected = _load("promotion_decision_0001.json")
    built = build_promotion_decision(**expected)
    assert built == expected


def test_build_rollback_record_matches_fixture() -> None:
    expected = _load("rollback_record_0001.json")
    built = build_rollback_record(**expected)
    assert built == expected


def test_build_gate_activation_record_matches_fixture() -> None:
    expected = _load("gate_activation_record_0001.json")
    built = build_gate_activation_record(**expected)
    assert built == expected


def test_build_graduation_record_matches_fixture() -> None:
    expected = _load("graduation_record_0001.json")
    built = build_graduation_record(**expected)
    assert built == expected


def test_build_lifecycle_artifact_graph_matches_fixture() -> None:
    expected = _load("lifecycle_artifact_graph_0001.json")
    built = build_lifecycle_artifact_graph(**expected)
    assert built == expected
