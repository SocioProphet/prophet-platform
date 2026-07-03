"""End-to-end conformance test for the promoted identity-prime kernel.

Runs the Michael trace through the kernel and validates the emitted proof
artifact against the CANONICAL platform schema
(``schemas/proof-artifact.schema.json``), not the toy reference schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from identity_prime.prime_kernel import (
    DEFAULT_TOPICS,
    decode_topics,
    encode_topics,
    run,
)

# apps/identity-prime/tests -> repo root is parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_SCHEMA = REPO_ROOT / "schemas" / "proof-artifact.schema.json"
MICHAEL_TRACE = Path(__file__).resolve().parent / "fixtures" / "michael_identity_prime_trace.jsonl"


def _validator() -> Draft202012Validator:
    schema = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _artifact() -> dict:
    return run(MICHAEL_TRACE.read_text(encoding="utf-8"))


def test_michael_artifact_validates_against_canonical_schema() -> None:
    artifact = _artifact()
    errors = sorted(_validator().iter_errors(artifact), key=lambda e: list(e.path))
    assert errors == [], "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_michael_trace_is_a_violation() -> None:
    # The proven behavior: the Michael trace fires a third-party pixel carrying
    # PATIENT/PARENT primes into an ad realm -> policy veto + nonce leak -> VIOLATION.
    artifact = _artifact()
    assert artifact["result"] == "VIOLATION"


def test_violation_carries_required_witness() -> None:
    # Canonical schema requires witness_or_counterexample when result==VIOLATION.
    artifact = _artifact()
    woc = artifact["witness_or_counterexample"]
    assert woc["violations"], "expected non-empty violations"
    kinds = {v["kind"] for v in woc["violations"]}
    # Forbidden prime co-occurrence, forbidden feature key, sensitive-prime-in-ad,
    # and the bounded-congruence nonce leak should all be present.
    assert "FORBIDDEN_PRIME_COOC" in kinds
    assert "FORBIDDEN_FEATURE_FOR_PRIME" in kinds
    assert "SENSITIVE_PRIME_IN_AD_REALM" in kinds
    assert "NONCE_STREAM_LEAK" in kinds


def test_artifact_binds_canonical_fields() -> None:
    # Spot-check the toy -> canonical mapping decisions.
    artifact = _artifact()
    assert artifact["schema_version"] == "0.1"
    assert artifact["claim"]["kind"] == "ifc_no_flow"
    assert artifact["precision"]["mode"] == "Exact"
    assert artifact["inputs_hash"].startswith("sha256:")
    assert set(artifact["domains"]) <= {
        "intervals", "signs", "octagon", "polyhedra", "nnc_polyhedra",
        "congruence", "sharing", "labels", "capabilities",
    }


def test_identity_is_prime_roundtrip() -> None:
    # The "identity is prime" basis: encode -> factor -> recover topics.
    code = encode_topics(["PATIENT", "PARENT"], DEFAULT_TOPICS)
    assert code == 3 * 5  # PATIENT=3, PARENT=5
    assert sorted(decode_topics(code, DEFAULT_TOPICS)) == ["PARENT", "PATIENT"]
