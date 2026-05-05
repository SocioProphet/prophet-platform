from __future__ import annotations

import json
from pathlib import Path

import pytest

from cell_service.extraction import ExtractionError, extract_from_pattern, extract_with_patterns

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "schemas/cell/watch-pattern-fixtures.json"


def load_fixtures() -> list[dict]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))["fixtures"]


@pytest.mark.parametrize("fixture", load_fixtures(), ids=lambda fixture: fixture["id"])
def test_extracts_expected_fixture_variables(fixture: dict) -> None:
    result = extract_from_pattern(fixture["watch_pattern"], fixture["input"])

    assert result.matched is True
    for key, value in fixture["expected_extractions"].items():
        assert result.extractions[key] == value
    assert result.confidence_score > 0


def test_phrase_pattern_match() -> None:
    result = extract_from_pattern(
        {"id": "pattern://phrase", "pattern_kind": "phrase", "raw_expression": "severe weather"},
        "Bucks County severe weather alert tonight.",
    )

    assert result.matched is True
    assert result.extractions == {}
    assert result.confidence_score == 1.0


def test_extract_with_patterns_selects_best_match() -> None:
    patterns = [
        {
            "id": "pattern://miss",
            "pattern_kind": "typed_template",
            "raw_expression": "$org acquired $target",
            "variables": [
                {"name": "org", "type": "entity", "required": True},
                {"name": "target", "type": "entity", "required": True},
            ],
        },
        {
            "id": "pattern://hit",
            "pattern_kind": "claim_template",
            "raw_expression": "$org released $product with $capability",
            "variables": [
                {"name": "org", "type": "entity", "required": True},
                {"name": "product", "type": "entity", "required": True},
                {"name": "capability", "type": "text", "required": True},
            ],
        },
    ]

    result = extract_with_patterns(patterns, "ExosphereHost released Runtime with failover orchestration.")

    assert result.pattern_id == "pattern://hit"
    assert result.extractions["org"] == "ExosphereHost"
    assert result.extractions["product"] == "Runtime"


def test_rejects_undeclared_template_variable() -> None:
    with pytest.raises(ExtractionError, match="undeclared variable"):
        extract_from_pattern(
            {
                "id": "pattern://bad",
                "pattern_kind": "typed_template",
                "raw_expression": "$known and $missing",
                "variables": [{"name": "known", "type": "word", "required": True}],
            },
            "alpha and beta",
        )


def test_rejects_unsupported_pattern_kind() -> None:
    with pytest.raises(ExtractionError, match="unsupported deterministic extraction"):
        extract_from_pattern(
            {"id": "pattern://semantic", "pattern_kind": "semantic", "raw_expression": "anything"},
            "anything",
        )
