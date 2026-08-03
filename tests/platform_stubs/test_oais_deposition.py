"""Teeth for oais-deposition — the OAIS preservation/curation vault check (#1272).

Proven BOTH ways (controls that fire):
  1. a well-formed deposition is ACCEPTED, and its AIP fixity matches the SHA-256
     of the real committed content bytes (fixity is verified, not asserted);
  2. an AIP with NO fixity is REJECTED;
  3. an AIP missing preservation metadata is REJECTED;
  4. a DIP whose fixity does not match the AIP fixity is REJECTED;
  5. a non-SHA-256 fixity algorithm is REJECTED;
  6. content that no longer hashes to the declared digest (tamper) is REJECTED;
  7. ingest_sip produces a self-consistent, schema-valid, ACCEPTED AIP;
  8. the committed example validates against the schema.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "eval"
EXAMPLE = SCHEMA_DIR / "examples" / "oais-deposition.example.json"
CONTENT = SCHEMA_DIR / "examples" / "oais-content" / "sherlock-stage2-r1.txt"


def _mod():
    path = ROOT / "tools" / "oais_deposition.py"
    spec = importlib.util.spec_from_file_location("oais_deposition", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _dep() -> dict:
    return json.loads(EXAMPLE.read_text())


# ── TEETH 1: well-formed deposition ACCEPTED, fixity matches real bytes ──
def test_example_accepted_and_fixity_matches_content():
    mod = _mod()
    v = mod.verify_deposition(_dep(), root=ROOT)
    assert v.accepted is True, v.reasons
    real = hashlib.sha256(CONTENT.read_bytes()).hexdigest()
    assert _dep()["aip"]["fixity"]["digest"] == real


# ── TEETH 2: AIP with no fixity is REJECTED ──
def test_missing_aip_fixity_is_rejected():
    mod = _mod()
    dep = _dep()
    del dep["aip"]["fixity"]
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("fixity" in r for r in v.reasons)


# ── TEETH 3: AIP missing preservation metadata is REJECTED ──
def test_missing_preservation_metadata_is_rejected():
    mod = _mod()
    dep = _dep()
    dep["aip"]["preservation_metadata"].pop("retention_tier")
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("preservation_metadata" in r for r in v.reasons)


# ── TEETH 4: DIP fixity that does not match the AIP fixity is REJECTED ──
def test_dip_fixity_mismatch_is_rejected():
    mod = _mod()
    dep = _dep()
    dep["dip"]["fixity"]["digest"] = "f" * 64  # valid shape, wrong value
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("does not match the AIP fixity" in r for r in v.reasons)


# ── TEETH 5: non-SHA-256 algorithm is REJECTED ──
def test_non_sha256_algorithm_is_rejected():
    mod = _mod()
    dep = _dep()
    dep["aip"]["fixity"]["algorithm"] = "MD5"
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("algorithm" in r for r in v.reasons)


# ── TEETH 6: content that no longer hashes to the declared digest is REJECTED ──
def test_tampered_content_is_rejected():
    mod = _mod()
    dep = _dep()
    # keep a valid-shaped digest that simply does not match the real bytes
    dep["aip"]["fixity"]["digest"] = "0" * 64
    dep["dip"]["fixity"]["digest"] = "0" * 64  # keep DIP==AIP so only the content check fires
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("does not match SIP content bytes" in r for r in v.reasons)


# ── TEETH 6b: a content_locator that does not resolve is REJECTED ──
# Fail-closed: content_locator is contract-required and points in-tree, so a
# deposition pointing at bytes which are not there leaves the fixity unverifiable
# and must not silently pass ("no bytes" != "faithful fixity").
def test_unresolvable_content_locator_is_rejected():
    mod = _mod()
    dep = _dep()
    dep["sip"]["content_locator"] = "schemas/eval/examples/oais-content/does-not-exist.txt"
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is False and any("does not resolve to a file" in r for r in v.reasons)


# ── TEETH 7: ingest_sip -> self-consistent, ACCEPTED, schema-valid AIP ──
def test_ingest_roundtrips_and_is_accepted():
    mod = _mod()
    content = b"hello preservation vault"
    dep = mod.ingest_sip(content, aip_id="aip-x", title="unit AIP", media_type="text/plain")
    assert dep["aip"]["fixity"]["digest"] == hashlib.sha256(content).hexdigest()
    # inline SIP has no resolvable path, so the byte-check is skipped; structure still ACCEPTED
    v = mod.verify_deposition(dep, root=ROOT)
    assert v.accepted is True, v.reasons
    schema = json.loads((SCHEMA_DIR / "oais-deposition.schema.json").read_text())
    jsonschema.validate(dep, schema)


# ── TEETH 8: committed example validates against the schema ──
def test_example_validates_against_schema():
    schema = json.loads((SCHEMA_DIR / "oais-deposition.schema.json").read_text())
    jsonschema.validate(_dep(), schema)
