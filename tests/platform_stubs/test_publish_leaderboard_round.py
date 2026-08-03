"""Teeth for publish-leaderboard-round — the public ranked/tiered round surface (#1272).

Proven BOTH ways (controls that fire):
  1. a round whose every entry passes validate_submission (#1271) PUBLISHES;
  2. a round containing an entry that FAILS a division gate is REJECTED;
  3. an OPEN round is flagged NON-comparable, and a declared comparable=true on
     an OPEN round is REJECTED (the division split is honoured);
  4. a declared `rank` that lies (disagrees with the ranking rule) is REJECTED;
  5. an entry whose headline is not the ranking metric is REJECTED;
  6. an entry whose submission is in the wrong division is REJECTED;
  7. the round contract + committed example validate against the schema.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "eval"
EXAMPLE = SCHEMA_DIR / "examples" / "leaderboard-round.closed.example.json"


def _mod():
    path = ROOT / "tools" / "publish_leaderboard_round.py"
    spec = importlib.util.spec_from_file_location("publish_leaderboard_round", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _round() -> dict:
    return json.loads(EXAMPLE.read_text())


# ── TEETH 1: all-valid round PUBLISHES ──
def test_all_valid_round_publishes():
    mod = _mod()
    v = mod.publish_round(_round())
    assert v.publishable is True, v.to_dict()
    assert v.comparable is True  # CLOSED
    ranked = v.to_dict()["ranked_entries"]
    assert [e["entry_id"] for e in ranked] == ["e-alpha", "e-beta"]
    assert [e["rank"] for e in ranked] == [1, 2]


# ── TEETH 2: an entry that fails a division gate makes the round NON-publishable ──
def test_round_with_failed_gate_entry_is_rejected():
    mod = _mod()
    rnd = _round()
    # break the second entry's clean-eval certificate -> fails a CLOSED (and OPEN) gate
    rnd["entries"][1]["submission"]["clean_eval_certificate"] = None
    v = mod.publish_round(rnd)
    assert v.publishable is False
    bad = [e for e in v.entries if e.entry_id == "e-beta"][0]
    assert not bad.valid and any("required gates" in r for r in bad.reasons)


# ── TEETH 3: OPEN is non-comparable; a lying comparable flag is rejected ──
def test_open_round_flagged_non_comparable():
    mod = _mod()
    rnd = _round()
    rnd["division"] = "OPEN"
    for e in rnd["entries"]:
        e["submission"]["division"] = "OPEN"
    del rnd["comparable"]
    v = mod.publish_round(rnd)
    assert v.publishable is True, v.to_dict()
    assert v.comparable is False  # OPEN is flagged non-comparable


def test_open_round_declaring_comparable_true_is_rejected():
    mod = _mod()
    rnd = _round()
    rnd["division"] = "OPEN"
    for e in rnd["entries"]:
        e["submission"]["division"] = "OPEN"
    rnd["comparable"] = True  # lies: OPEN is never comparable
    v = mod.publish_round(rnd)
    assert v.publishable is False
    assert any("contradicts division" in r for r in v.reasons)


# ── TEETH 4: a declared rank that lies is rejected ──
def test_lying_declared_rank_is_rejected():
    mod = _mod()
    rnd = _round()
    rnd["entries"][0]["rank"] = 2  # alpha has the higher score -> computed rank 1
    rnd["entries"][1]["rank"] = 1
    v = mod.publish_round(rnd)
    assert v.publishable is False
    assert any("computed rank" in r for e in v.entries for r in e.reasons)


# ── TEETH 5: headline metric must be the ranking metric ──
def test_headline_metric_mismatch_is_rejected():
    mod = _mod()
    rnd = _round()
    rnd["entries"][0]["headline"]["metric_id"] = "md.some.other"
    v = mod.publish_round(rnd)
    assert v.publishable is False
    assert any("ranking metric" in r for e in v.entries for r in e.reasons)


# ── TEETH 6: entry submission must be in the round's division ──
def test_entry_wrong_division_is_rejected():
    mod = _mod()
    rnd = _round()
    rnd["entries"][1]["submission"]["division"] = "OPEN"  # round is CLOSED
    v = mod.publish_round(rnd)
    assert v.publishable is False
    assert any("division" in r for e in v.entries for r in e.reasons)


# ── TEETH 7: contract + example validate against the schema ──
def test_round_validates_against_schema():
    schema = json.loads((SCHEMA_DIR / "leaderboard-round.schema.json").read_text())
    jsonschema.validate(_round(), schema)
