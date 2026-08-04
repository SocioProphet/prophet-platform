#!/usr/bin/env python3
"""Validator for contracts/memory/vector-chunk.v0.json (GAP-ER-1).

Checks:
  - Schema validation of the VectorChunk contract using jsonschema
  - Structural boundary: chunk_id format (vc- prefix), non-empty object_id + embedding_ref
  - Scope envelope presence: topic_set non-empty, domain non-empty
  - Span consistency when present: end >= start
  - Non-claim: does NOT verify that object_id resolves against a live FAIR_OBJECT registry

Expects the valid example to pass and both invalid examples to fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema not installed — run: pip install jsonschema")

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "memory" / "vector-chunk.v0.json"
VALID_EXAMPLE = ROOT / "contracts" / "memory" / "vector-chunk.v0.valid.example.json"
INVALID_MISSING_SCOPE = ROOT / "contracts" / "memory" / "vector-chunk.v0.invalid-missing-scope.example.json"
INVALID_NO_OBJECT_ID = ROOT / "contracts" / "memory" / "vector-chunk.v0.invalid-no-object-id.example.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(instance: dict, schema: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(schema)
    return [e.message for e in sorted(v.iter_errors(instance), key=str)]


def validate_chunk_id(chunk: dict) -> list[str]:
    problems: list[str] = []
    cid = chunk.get("chunk_id", "")
    if not cid.startswith("vc-"):
        problems.append(f"chunk_id must begin with 'vc-', got: {cid!r}")
    return problems


def validate_span(chunk: dict) -> list[str]:
    problems: list[str] = []
    span = chunk.get("scope", {}).get("span")
    if span is not None:
        if span.get("end", 0) < span.get("start", 0):
            problems.append(f"scope.span.end ({span['end']}) must be >= start ({span['start']})")
    return problems


def main() -> int:
    schema = load_schema()
    problems: list[str] = []

    valid_data = json.loads(VALID_EXAMPLE.read_text(encoding="utf-8"))
    schema_errors = validate(valid_data, schema)
    if schema_errors:
        problems.append(f"valid example failed schema: {schema_errors}")
    problems.extend(validate_chunk_id(valid_data))
    problems.extend(validate_span(valid_data))

    missing_scope = json.loads(INVALID_MISSING_SCOPE.read_text(encoding="utf-8"))
    if not validate(missing_scope, schema):
        problems.append("invalid-missing-scope example should fail schema but passed")

    no_object_id = json.loads(INVALID_NO_OBJECT_ID.read_text(encoding="utf-8"))
    if not validate(no_object_id, schema):
        problems.append("invalid-no-object-id example should fail schema but passed")

    report = {
        "validator": "prophet-platform.vector-chunk-contract.validator.v0",
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Does not verify object_id resolves against a live FAIR_OBJECT registry.",
            "Does not execute memory queries or vector lookups.",
            "Does not validate vector coordinates — those live in embedding_ref.",
        ],
    }
    print(json.dumps(report, indent=2))
    print(("PASS" if not problems else "FAIL") + ": VectorChunk contract (GAP-ER-1)")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
