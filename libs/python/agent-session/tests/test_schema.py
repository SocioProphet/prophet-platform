from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from agent_session.schema import generable, is_generable, schema_instruction, parse_response


@generable
class Trip(BaseModel):
    destination: str
    days: int
    highlights: list[str]


class NotGenerable(BaseModel):
    name: str


def test_generable_marks_class() -> None:
    assert is_generable(Trip)


def test_non_generable_class_is_rejected() -> None:
    assert not is_generable(NotGenerable)


def test_non_pydantic_class_is_rejected() -> None:
    assert not is_generable(str)


def test_schema_instruction_includes_json_schema() -> None:
    instruction = schema_instruction(Trip)
    assert "JSON" in instruction
    assert "destination" in instruction


def test_parse_response_round_trips() -> None:
    raw = json.dumps({"destination": "Tokyo", "days": 4, "highlights": ["Shibuya", "Asakusa"]})
    result = parse_response(Trip, raw)
    assert result.destination == "Tokyo"
    assert result.days == 4
    assert "Shibuya" in result.highlights


def test_parse_response_strips_markdown_fences() -> None:
    raw = '```json\n{"destination": "Kyoto", "days": 3, "highlights": []}\n```'
    result = parse_response(Trip, raw)
    assert result.destination == "Kyoto"


def test_parse_response_raises_on_invalid_json() -> None:
    with pytest.raises(Exception):
        parse_response(Trip, "not json at all")
