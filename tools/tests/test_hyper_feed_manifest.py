"""Theorems of the Hyper Feed manifest (tools.hyper_feed.manifest) — node-symmetric federation:
match by Hamming without moving raw data, verify by digest, op_set-scoped. Deterministic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.hyper_feed import manifest as hf

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/crystal-atlas/schemas/hyper-feed-manifest.v0.schema.json"


def _entry(ref, code, op_set="discourse", content=b"x"):
    return {"ref_id": ref, "op_set": op_set, "code": code, "digest": hf.content_digest(content),
            "attestation_ref": f"att:{ref}"}


def test_hamming_hex():
    assert hf.hamming_hex("00", "00") == 0
    assert hf.hamming_hex("00", "01") == 1
    assert hf.hamming_hex("ff", "00") == 8
    with pytest.raises(ValueError):
        hf.hamming_hex("ff", "ffff")  # different length is incomparable


def test_match_finds_near_codes_and_skips_far():
    # THEOREM: a peer discovers "who has something like this" by Hamming on codes — no raw data moves.
    m = hf.build_manifest("nodeA", "t1", [_entry("r_near", "ff01"), _entry("r_far", "0000")], now="T")
    assert hf.match("ff00", m, max_hamming=4) == [("r_near", 1)]  # far one excluded


def test_match_is_op_set_scoped():
    # THEOREM: federation respects isolation — a peer only matches within an op_set it queries.
    m = hf.build_manifest("nodeA", "t1", [
        _entry("r_ok", "ff00", op_set="discourse"),
        _entry("r_other", "ff00", op_set="finance"),
    ], now="T")
    assert hf.match("ff00", m, max_hamming=2, op_set="discourse") == [("r_ok", 0)]


def test_digest_verifies_and_rejects_tamper():
    # THEOREM: a fetched object is trusted only if it content-addresses to the manifest's digest.
    e = _entry("r1", "ff00", content=b"hello")
    assert hf.verify_digest(e, b"hello") is True
    assert hf.verify_digest(e, b"HELLO") is False


def test_manifest_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text())
    good = hf.build_manifest("nodeA", "t1", [_entry("r1", "ff00")], now="2026-08-04T00:00:00Z")
    jsonschema.validate(good, schema)  # must not raise
    bad = hf.build_manifest("nodeA", "t1", [{"ref_id": "r1", "op_set": "d", "code": "XYZ", "digest": "d"}], now="T")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)  # code "XYZ" is not hex
