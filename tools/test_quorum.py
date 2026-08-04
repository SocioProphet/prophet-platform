#!/usr/bin/env python3
"""Tests for the validator-quorum gate — fail-closed, schema-conformant, threshold-correct."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from quorum import compose_quorum_proof, parse_rule, quorum_gate, verify_quorum  # noqa: E402

V = ["spiffe://validators/h1", "spiffe://validators/h2", "spiffe://validators/h3"]
PH = "sha256:" + "a" * 64


def _sig(vid, s="MEUCIQD" + "f" * 20):
    return {"kind": "human", "spiffe_id": vid, "sig": s}


def _proof(sigs, rule="2of3-human", validators=None, phash=PH):
    return compose_quorum_proof(rule, validators or V, phash, sigs)


# ── rule parsing ─────────────────────────────────────────────────────────────
def test_parse_valid_rule():
    r = parse_rule("2of3-human")
    assert r and r.threshold == 2 and r.total == 3 and r.kind == "human"


def test_parse_rejects_threshold_gt_total():
    assert parse_rule("4of3-human") is None


def test_parse_rejects_malformed():
    assert parse_rule("two-of-three") is None and parse_rule("") is None


# ── verify_quorum: fail-closed ───────────────────────────────────────────────
def test_valid_two_of_three_accepted():
    ok, why = verify_quorum(_proof([_sig(V[0]), _sig(V[1])]), payload_hash=PH)
    assert ok, why


def test_below_threshold_rejected():
    ok, _ = verify_quorum(_proof([_sig(V[0])]))
    assert not ok


def test_non_validator_signer_rejected():
    ok, why = verify_quorum(_proof([_sig(V[0]), _sig("spiffe://validators/intruder")]))
    assert not ok and any("not a listed" in x for x in why)


def test_duplicate_signer_not_counted_twice():
    ok, why = verify_quorum(_proof([_sig(V[0]), _sig(V[0])]))
    assert not ok and any("duplicate" in x for x in why)


def test_payload_hash_binding():
    ok, why = verify_quorum(_proof([_sig(V[0]), _sig(V[1])]), payload_hash="sha256:" + "b" * 64)
    assert not ok and any("does not match" in x for x in why)


def test_bad_payload_hash_format_rejected():
    ok, _ = verify_quorum(_proof([_sig(V[0]), _sig(V[1])], phash="not-a-hash"))
    assert not ok


def test_kind_mismatch_rejected():
    sigs = [{"kind": "machine", "spiffe_id": V[0], "sig": "x" * 20},
            {"kind": "machine", "spiffe_id": V[1], "sig": "x" * 20}]
    ok, _ = verify_quorum(_proof(sigs))
    assert not ok


def test_missing_field_rejected():
    ok, why = verify_quorum({"rule": "2of3-human", "validators": V, "signatures": [_sig(V[0])]})
    assert not ok and any("signed_payload_hash" in x for x in why)


def test_too_few_validators_for_rule_rejected():
    ok, _ = verify_quorum(compose_quorum_proof("2of3-human", V[:2], PH, [_sig(V[0]), _sig(V[1])]))
    assert not ok


# ── Genesis Guard gate ───────────────────────────────────────────────────────
def test_below_floor_needs_no_quorum():
    g = quorum_gate(2, floor_rank=3, proof=None)
    assert g["quorum_required"] is False and g["quorum_ok"]


def test_at_floor_with_valid_quorum_admits():
    g = quorum_gate(3, floor_rank=3, proof=_proof([_sig(V[0]), _sig(V[1])]), payload_hash=PH)
    assert g["quorum_ok"] and g["granted_rank"] == 3


def test_advisory_records_unmet_without_demote():
    g = quorum_gate(3, floor_rank=3, proof=None, enforce=False)
    assert g["quorum_required"] and not g["quorum_ok"] and g["granted_rank"] == 3


def test_enforce_demotes_unmet_quorum():
    g = quorum_gate(4, floor_rank=3, proof=None, enforce=True)
    assert g.get("demoted") and g["granted_rank"] == 2


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python3", "-m", "pytest", "-q", __file__]))
