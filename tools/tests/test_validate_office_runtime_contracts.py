"""Tests for SourceOS office runtime contract validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import validate_office_runtime_contracts  # noqa: E402


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_office_runtime_contract_examples_validate():
    assert validate_office_runtime_contracts.main() == 0


def test_closed_provider_adapter_cannot_be_core_authority():
    schema = _load_json(ROOT / "schemas" / "office" / "office_adapter_profile.schema.json")
    example = _load_json(ROOT / "schemas" / "office" / "examples" / "office_adapter_profile.example.json")
    example["authority_scope"] = "CORE_AUTHORITY"
    example["enabled_by_default"] = True
    example["runtime_dependency"] = True
    example["adapter_type"] = "OPEN_RUNTIME"

    errors = list(Draft202012Validator(schema).iter_errors(example))

    assert errors
    assert any(
        "CORE_AUTHORITY" in error.message
        or "False was expected" in error.message
        or "OPEN_RUNTIME" in error.message
        for error in errors
    )
