#!/usr/bin/env python3
"""Validates telephony ingress CallEventEnvelope fixtures against the schema and policy gates."""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("FAIL: jsonschema not installed — run: pip install jsonschema")
    sys.exit(1)

SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "telephony-ingress" / "call-event-envelope.schema.v0.1.json"
FIXTURES_DIR = Path(__file__).parent.parent / "contracts" / "telephony-ingress"


class PolicyViolation(Exception):
    pass


def ok(msg):
    print(f"  ok  {msg}")


def fail(msg):
    print(f"FAIL  {msg}")
    sys.exit(1)


def policy_gates(doc, label):
    non_claims = doc.get("non_claims")
    if not non_claims:
        raise PolicyViolation("non_claims must be a non-empty array")

    policy_decision_ref = doc.get("policy_decision_ref")

    if doc.get("transcript_ref") and not policy_decision_ref:
        raise PolicyViolation("transcript_ref present but policy_decision_ref is missing — transcript access requires a policy decision")

    if doc.get("recording_ref") and not policy_decision_ref:
        raise PolicyViolation("recording_ref present but policy_decision_ref is missing — recording access requires a policy decision")


def validate_valid(schema, path):
    doc = json.loads(path.read_text())
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as e:
        fail(f"{path.name}: schema rejected valid fixture — {e.message}")
    try:
        policy_gates(doc, path.name)
    except PolicyViolation as e:
        fail(f"{path.name}: policy gate rejected valid fixture — {e}")
    ok(f"{path.name}: valid fixture accepted")


def validate_reject(schema, path):
    doc = json.loads(path.read_text())
    doc_stripped = {k: v for k, v in doc.items() if not k.startswith("_")}
    try:
        jsonschema.validate(doc_stripped, schema)
    except jsonschema.ValidationError:
        ok(f"{path.name}: reject fixture correctly refused by schema")
        return
    try:
        policy_gates(doc_stripped, path.name)
    except PolicyViolation:
        ok(f"{path.name}: reject fixture correctly refused by policy gate")
        return
    fail(f"{path.name}: reject fixture was accepted — should have been refused")


def main():
    if not SCHEMA_PATH.exists():
        fail(f"schema not found: {SCHEMA_PATH}")

    schema = json.loads(SCHEMA_PATH.read_text())

    valid_fixtures = sorted(FIXTURES_DIR.glob("valid.*.json"))
    reject_fixtures = sorted(FIXTURES_DIR.glob("reject.*.json"))

    if not valid_fixtures:
        fail("no valid.*.json fixtures found in contracts/telephony-ingress/")
    if not reject_fixtures:
        fail("no reject.*.json fixtures found in contracts/telephony-ingress/")

    print("=== telephony-ingress: valid fixtures ===")
    for path in valid_fixtures:
        validate_valid(schema, path)

    print("=== telephony-ingress: reject fixtures ===")
    for path in reject_fixtures:
        validate_reject(schema, path)

    print(f"\ntelephony-ingress: {len(valid_fixtures)} valid, {len(reject_fixtures)} reject — all passed")


if __name__ == "__main__":
    main()
