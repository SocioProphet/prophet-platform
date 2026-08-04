"""Tests for validate_vector_chunk_contract.py + vector-chunk.v0.json schema (GAP-ER-1)."""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validate_vector_chunk_contract import (
    load_schema, validate, validate_chunk_id, validate_span,
    VALID_EXAMPLE, INVALID_MISSING_SCOPE, INVALID_NO_OBJECT_ID, SCHEMA_PATH,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _valid() -> dict:
    return json.loads(VALID_EXAMPLE.read_text(encoding="utf-8"))


def _missing_scope() -> dict:
    return json.loads(INVALID_MISSING_SCOPE.read_text(encoding="utf-8"))


def _no_object_id() -> dict:
    return json.loads(INVALID_NO_OBJECT_ID.read_text(encoding="utf-8"))


def _chunk(**overrides) -> dict:
    base = {
        "chunk_id": "vc-aabbccddeeff",
        "object_id": "fair:test:obj:001",
        "embedding_ref": "ec-001122334455",
        "scope": {"topic_set": ["test.topic"], "domain": "test"},
        "indexed_at": "2026-08-04T00:00:00Z",
    }
    base.update(overrides)
    return base


# ── schema file ───────────────────────────────────────────────────────────────

def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"


def test_schema_is_valid_json():
    schema = load_schema()
    assert isinstance(schema, dict)


def test_schema_has_required_fields():
    schema = load_schema()
    assert "chunk_id" in schema["required"]
    assert "object_id" in schema["required"]
    assert "embedding_ref" in schema["required"]
    assert "scope" in schema["required"]
    assert "indexed_at" in schema["required"]


# ── valid example ─────────────────────────────────────────────────────────────

def test_valid_example_passes_schema():
    schema = load_schema()
    errors = validate(_valid(), schema)
    assert errors == [], f"Valid example has errors: {errors}"


def test_valid_example_has_expected_chunk_id():
    data = _valid()
    assert data["chunk_id"].startswith("vc-")


def test_valid_example_has_scope():
    data = _valid()
    assert "scope" in data
    assert "topic_set" in data["scope"]
    assert "domain" in data["scope"]


def test_valid_example_topic_set_non_empty():
    data = _valid()
    assert len(data["scope"]["topic_set"]) >= 1


def test_valid_example_span_consistent():
    data = _valid()
    span = data["scope"].get("span")
    if span:
        assert span["end"] >= span["start"]


# ── invalid examples ──────────────────────────────────────────────────────────

def test_missing_scope_fails_schema():
    schema = load_schema()
    errors = validate(_missing_scope(), schema)
    assert errors, "Missing-scope example should fail schema"


def test_no_object_id_fails_schema():
    schema = load_schema()
    errors = validate(_no_object_id(), schema)
    assert errors, "No-object-id example should fail schema"


# ── field-level schema checks ─────────────────────────────────────────────────

def test_missing_chunk_id_fails():
    schema = load_schema()
    c = _chunk()
    del c["chunk_id"]
    assert validate(c, schema)


def test_missing_object_id_fails():
    schema = load_schema()
    c = _chunk()
    del c["object_id"]
    assert validate(c, schema)


def test_missing_embedding_ref_fails():
    schema = load_schema()
    c = _chunk()
    del c["embedding_ref"]
    assert validate(c, schema)


def test_missing_indexed_at_fails():
    schema = load_schema()
    c = _chunk()
    del c["indexed_at"]
    assert validate(c, schema)


def test_empty_topic_set_fails():
    schema = load_schema()
    c = _chunk(scope={"topic_set": [], "domain": "test"})
    assert validate(c, schema)


def test_empty_domain_fails():
    schema = load_schema()
    c = _chunk(scope={"topic_set": ["test"], "domain": ""})
    assert validate(c, schema)


def test_missing_domain_fails():
    schema = load_schema()
    c = _chunk(scope={"topic_set": ["test"]})
    assert validate(c, schema)


def test_missing_topic_set_fails():
    schema = load_schema()
    c = _chunk(scope={"domain": "test"})
    assert validate(c, schema)


def test_additional_properties_disallowed():
    schema = load_schema()
    c = _chunk(unknown_field="bad")
    assert validate(c, schema)


def test_vector_dim_must_be_positive():
    schema = load_schema()
    c = _chunk(vector_dim=0)
    assert validate(c, schema)


def test_valid_with_optional_vector_dim():
    schema = load_schema()
    c = _chunk(vector_dim=1536)
    assert validate(c, schema) == []


def test_valid_with_optional_collection_ref():
    schema = load_schema()
    c = _chunk(collection_ref="memoryd-medical-v1")
    assert validate(c, schema) == []


def test_span_valid_when_present():
    schema = load_schema()
    c = _chunk(scope={"topic_set": ["t"], "domain": "d", "span": {"start": 0, "end": 512}})
    assert validate(c, schema) == []


def test_span_end_less_than_start_caught_by_semantic_check():
    c = _chunk(scope={"topic_set": ["t"], "domain": "d", "span": {"start": 100, "end": 50}})
    problems = validate_span(c)
    assert problems, "Should catch end < start"


def test_span_end_equals_start_ok():
    c = _chunk(scope={"topic_set": ["t"], "domain": "d", "span": {"start": 50, "end": 50}})
    assert validate_span(c) == []


# ── chunk_id format check ─────────────────────────────────────────────────────

def test_chunk_id_vc_prefix_required():
    c = _chunk(chunk_id="bad-id-001")
    problems = validate_chunk_id(c)
    assert problems, "Should reject non-vc- prefix"


def test_chunk_id_vc_prefix_passes():
    c = _chunk(chunk_id="vc-abc123def456")
    assert validate_chunk_id(c) == []


# ── non-claim: does NOT validate object_id resolves live ─────────────────────

def test_arbitrary_object_id_passes_schema():
    schema = load_schema()
    c = _chunk(object_id="some-opaque-object-ref-not-resolved")
    assert validate(c, schema) == []
