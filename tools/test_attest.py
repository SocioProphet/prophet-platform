"""Coverage for tools/attest.py — standards-conformant SLSA/in-toto/DSSE attestation.

Pins the properties that make this externally verifiable rather than self-issued: the statement
conforms to in-toto v1 + SLSA v1, the DSSE pre-authentication encoding matches the spec byte-for-
byte (so cosign/any DSSE verifier agrees), sign->verify round-trips, and a tampered payload fails.
Our governance (verdict/marker-proof/receipt-digest) rides inside the standard predicate.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("attest", ROOT / "tools" / "attest.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["attest"] = m
    spec.loader.exec_module(m)
    return m


attest = _load()

RECEIPT = {
    "tool": "prophet-platform.revendor_engine.v1",
    "idempotency_key": "hellgraph-engine@hellgraph-service@0.4.40->0.4.45",
    "to_version": "0.4.45", "consumers": ["hellgraph-service"],
    "requested_by_event_ref": "evt-1", "status": "applied", "requires_human_approval": False,
    "steps": [{"step": "assert_marker", "ok": True, "evidence": {
        "expected_present": ['PROP_NS = "prop:"'], "member": "package/ts/dist/index.js",
        "tarball_digest": "sha256:abc"}}],
    "receipt_digest": "sha256:deadbeef",
}
DIGEST = "sha256:" + "a" * 64


def test_statement_conforms_to_intoto_and_slsa_with_governance():
    s = attest.build_statement("socioprophet-hellgraph-0.4.45.tgz", DIGEST, RECEIPT)
    assert s["_type"] == attest.IN_TOTO_STATEMENT_TYPE
    assert s["predicateType"] == attest.SLSA_PREDICATE_TYPE
    assert s["subject"][0]["digest"]["sha256"] == "a" * 64  # 'sha256:' prefix stripped
    bd = s["predicate"]["buildDefinition"]
    assert bd["buildType"] and "builder" in s["predicate"]["runDetails"]
    gov = bd["internalParameters"]["governance"]
    assert gov["receipt_digest"] == "sha256:deadbeef" and gov["fail_closed"] is True
    assert gov["marker_proof"]["expected_present"] == ['PROP_NS = "prop:"']


def test_dsse_pae_matches_the_spec_byte_for_byte():
    # DSSEv1 SP LEN(type) SP type SP LEN(payload) SP payload
    assert attest.dsse_pae("application/vnd.in-toto+json", b"hello") \
        == b"DSSEv1 28 application/vnd.in-toto+json 5 hello"


def test_sign_then_verify_round_trips():
    s = attest.build_statement("x.tgz", DIGEST, RECEIPT)
    key = b"k" * 32
    env = attest.sign_envelope(s, attest.hmac_signer(key), keyid="test")
    assert env["payloadType"] == attest.DSSE_PAYLOAD_TYPE
    assert attest.verify_envelope(env, attest.hmac_verifier(key)) is True
    assert json.loads(base64.standard_b64decode(env["payload"])) == s


def test_tampered_payload_fails_verification():
    s = attest.build_statement("x.tgz", DIGEST, RECEIPT)
    key = b"k" * 32
    env = attest.sign_envelope(s, attest.hmac_signer(key))
    payload = json.loads(base64.standard_b64decode(env["payload"]))
    payload["predicate"]["buildDefinition"]["internalParameters"]["governance"]["status"] = "tampered"
    env["payload"] = base64.standard_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode()
    assert attest.verify_envelope(env, attest.hmac_verifier(key)) is False


def test_wrong_key_fails():
    env = attest.sign_envelope(attest.build_statement("x.tgz", DIGEST, RECEIPT), attest.hmac_signer(b"k" * 32))
    assert attest.verify_envelope(env, attest.hmac_verifier(b"different-key")) is False


def test_bad_digest_rejected():
    with pytest.raises(ValueError, match="hex"):
        attest.build_statement("x.tgz", "notadigest", RECEIPT)


def test_main_emits_a_verifiable_envelope(tmp_path, monkeypatch):
    r = tmp_path / "r.json"
    r.write_text(json.dumps(RECEIPT))
    out = tmp_path / "att.json"
    monkeypatch.setenv("ATTEST_HMAC_KEY", "testkey")
    assert attest.main(["--receipt", str(r), "--subject-name", "x.tgz",
                        "--subject-digest", DIGEST, "--out", str(out)]) == 0
    env = json.loads(out.read_text())
    assert attest.verify_envelope(env, attest.hmac_verifier(b"testkey")) is True
