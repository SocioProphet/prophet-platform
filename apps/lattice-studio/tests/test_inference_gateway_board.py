"""The InferenceGateway board projects into the cloud catalog, schema-conformant.

Validates against the real contracts/crystal-atlas/schemas/model-catalog-entry.v0.schema.json
(no external dep — the schema is strict: additionalProperties=false), and asserts the
sovereignty encoding that makes the board rank sovereignty-aware.
"""
from __future__ import annotations

import json
from pathlib import Path

from lattice_studio.inference_gateway_board import (
    board_catalog_entries, foundation_entries, business_champion_entries,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((REPO_ROOT / "contracts" / "crystal-atlas" / "schemas"
                     / "model-catalog-entry.v0.schema.json").read_text())

_TYPES = {"string": str, "boolean": bool, "array": list, "number": (int, float), "object": dict}


def _validate(entry: dict) -> list[str]:
    errs = []
    for k in SCHEMA.get("required", []):
        if k not in entry:
            errs.append(f"missing required {k}")
    if SCHEMA.get("additionalProperties") is False:
        for k in entry:
            if k not in SCHEMA["properties"]:
                errs.append(f"additional property {k}")
    for k, v in entry.items():
        spec = SCHEMA["properties"].get(k)
        if spec and spec.get("type") in _TYPES and not isinstance(v, _TYPES[spec["type"]]):
            errs.append(f"{k} wrong type")
    return errs


def test_every_board_entry_conforms_to_model_catalog_entry_v0():
    for e in board_catalog_entries():
        assert _validate(e) == [], f"{e['model_id']}: {_validate(e)}"


def test_board_unites_foundation_and_business_models():
    ids = {e["model_id"] for e in board_catalog_entries()}
    assert "claude-opus-4-8" in ids           # foundation (vendor)
    assert "llama-3.3-70b" in ids             # foundation (open-weight, intersection)
    assert "gbm-fraud-v4" in ids              # business champion
    assert len(board_catalog_entries()) == len(foundation_entries()) + len(business_champion_entries())


def test_sovereignty_is_encoded_and_honest():
    by = {e["model_id"]: e["privacy_profile"] for e in board_catalog_entries()}
    assert by["claude-opus-4-8"] == "vendor-cloud"        # not client-owned — honest
    assert by["gemma-2-9b-it"] == "sovereign-local"       # fully local
    assert by["llama-3.3-70b"] == "sovereign-both"        # the client-owned intersection
    # every business model is client-owned/sovereign
    for e in business_champion_entries():
        assert e["privacy_profile"].startswith("sovereign")


def test_no_business_champion_claims_vendor_lock():
    assert all(e["privacy_profile"] != "vendor-cloud" for e in business_champion_entries())
