"""Conformance + teeth tests for the Intelligence-Superiority feature-board.

validate_intelligence_superiority_board.py's docstring claims each of its 5 TEETH is "proven both
ways" here: a violation gets REJECTED, and the same board with the violation fixed is not rejected
for that reason. This file makes that claim true.

Also guards the two things a governed, sealed dataset must never regress:
  1. the committed board (schemas/eval/examples/intelligence-superiority-board.json) is byte-in-sync
     with tools/emit_intelligence_superiority_board.py (same drift discipline as --check);
  2. the committed board validates against both the JSON-Schema shape AND validate_board's teeth,
     and seals to a stable SHA-256 receipt.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "eval" / "intelligence-superiority-board.schema.json"
BOARD_PATH = ROOT / "schemas" / "eval" / "examples" / "intelligence-superiority-board.json"


def _load(name: str, relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # dataclasses on 3.12 resolve cls.__module__ via sys.modules; register before exec_module.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _validator():
    return _load("is_board_validator", "tools/validate_intelligence_superiority_board.py")


def _emitter():
    return _load("is_board_emitter", "tools/emit_intelligence_superiority_board.py")


def _minimal_valid_board() -> dict:
    """Smallest board that satisfies every tooth — the baseline every negative test mutates."""
    return {
        "board_id": "test-board",
        "title": "Test Board",
        "generated_ts": "2026-08-03T00:00:00Z",
        "spec_version": "1.0.0",
        "categories": [
            {
                "category_id": "rag",
                "name": "RAG",
                "description": "test category",
                "competitors": ["Glean"],
                "litmus_features": [
                    {"feature_id": "breadth", "name": "Breadth",
                     "definition": "def", "criteria": "criteria"},
                ],
                "scores": [
                    {
                        "feature_id": "breadth",
                        "competitor": "Glean",
                        "verdict": "BEAT",
                        "maturity": "live",
                        "assessment_basis": "self_assessed",
                        "evidence_ref": [{"repo": "a"}, {"repo": "b"}],
                    },
                ],
            },
        ],
    }


# ── TOOTH 1: a category with no litmus_features is REJECTED ─────────────────────────────────────

def test_tooth1_category_with_no_litmus_features_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["litmus_features"] = []
    result = v.validate_board(board)
    assert not result.valid
    assert any("no litmus_features" in r for r in result.rejections)


def test_tooth1_category_with_litmus_features_is_not_rejected_for_that_reason():
    v = _validator()
    result = v.validate_board(_minimal_valid_board())
    assert not any("no litmus_features" in r for r in result.rejections)


# ── TOOTH 2: a BEAT/MEET verdict with no evidence_ref is REJECTED ───────────────────────────────

def test_tooth2_lead_verdict_without_evidence_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["evidence_ref"] = []
    result = v.validate_board(board)
    assert not result.valid
    assert any("has no evidence_ref" in r for r in result.rejections)


def test_tooth2_lead_verdict_with_evidence_is_not_rejected_for_that_reason():
    v = _validator()
    result = v.validate_board(_minimal_valid_board())
    assert not any("has no evidence_ref" in r for r in result.rejections)


def test_tooth2_partial_and_gap_verdicts_need_no_evidence():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["verdict"] = "GAP"
    board["categories"][0]["scores"][0]["evidence_ref"] = []
    result = v.validate_board(board)
    assert result.valid


# ── TOOTH 3: externally_certified with no cert_ref is REJECTED ──────────────────────────────────

def test_tooth3_externally_certified_without_cert_ref_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["assessment_basis"] = "externally_certified"
    result = v.validate_board(board)
    assert not result.valid
    assert any("externally_certified but no cert_ref" in r for r in result.rejections)


def test_tooth3_externally_certified_with_cert_ref_is_not_rejected_for_that_reason():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["assessment_basis"] = "externally_certified"
    board["categories"][0]["scores"][0]["cert_ref"] = "cert-123"
    result = v.validate_board(board)
    assert not any("externally_certified but no cert_ref" in r for r in result.rejections)


# ── TOOTH 4: orphan scores (unknown feature_id / competitor) are REJECTED ───────────────────────

def test_tooth4_score_with_undeclared_feature_id_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["feature_id"] = "not-a-real-feature"
    result = v.validate_board(board)
    assert not result.valid
    assert any("is not a declared litmus_feature" in r for r in result.rejections)


def test_tooth4_score_with_undeclared_competitor_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["competitor"] = "NotACompetitor"
    result = v.validate_board(board)
    assert not result.valid
    assert any("is not in the category competitors" in r for r in result.rejections)


def test_tooth4_score_with_declared_feature_and_competitor_is_not_rejected_for_that_reason():
    v = _validator()
    result = v.validate_board(_minimal_valid_board())
    assert not any("is not a declared litmus_feature" in r or "is not in the category competitors" in r
                   for r in result.rejections)


# ── TOOTH 5: a thin BEAT/MEET (spec OR <MIN_EVIDENCE_REFS) without provisional=true is REJECTED ──

def test_tooth5_thin_spec_lead_without_provisional_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["maturity"] = "spec"
    result = v.validate_board(board)
    assert not result.valid
    assert any("is thin" in r and "provisional=true" in r for r in result.rejections)


def test_tooth5_thin_underevidenced_lead_without_provisional_is_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["evidence_ref"] = [{"repo": "a"}]  # 1 < MIN_EVIDENCE_REFS
    result = v.validate_board(board)
    assert not result.valid
    assert any("is thin" in r and "provisional=true" in r for r in result.rejections)


def test_tooth5_thin_lead_with_provisional_true_is_not_rejected():
    v = _validator()
    board = _minimal_valid_board()
    board["categories"][0]["scores"][0]["maturity"] = "spec"
    board["categories"][0]["scores"][0]["provisional"] = True
    result = v.validate_board(board)
    assert result.valid


def test_tooth5_non_thin_live_lead_needs_no_provisional_flag():
    v = _validator()
    result = v.validate_board(_minimal_valid_board())  # live, 2 evidence_refs
    assert result.valid
    assert not result.tally["provisional"]


# ── Sealing is deterministic ─────────────────────────────────────────────────────────────────────

def test_seal_is_deterministic_for_the_same_board():
    v = _validator()
    board = _minimal_valid_board()
    result = v.validate_board(board)
    r1 = v.seal(copy.deepcopy(board), result)
    r2 = v.seal(copy.deepcopy(board), result)
    assert r1["sha256"] == r2["sha256"]


def test_seal_changes_if_the_board_changes():
    v = _validator()
    board = _minimal_valid_board()
    result = v.validate_board(board)
    r1 = v.seal(copy.deepcopy(board), result)
    board["title"] = "Different Title"
    r2 = v.seal(board, result)
    assert r1["sha256"] != r2["sha256"]


# ── Integration: the committed board is the real thing, and it is honest ────────────────────────

def test_committed_board_matches_the_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(board, schema)


def test_committed_board_passes_every_tooth():
    v = _validator()
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    result = v.validate_board(board)
    assert result.valid, result.rejections


def test_committed_board_is_in_sync_with_the_emitter():
    # Same drift guard as `emit_intelligence_superiority_board.py --check`, run in-process.
    emitter = _emitter()
    board = emitter.build_board()
    text = emitter.render(board)
    assert BOARD_PATH.read_text(encoding="utf-8") == text, (
        "schemas/eval/examples/intelligence-superiority-board.json is out of sync with "
        "tools/emit_intelligence_superiority_board.py — re-run `python3 "
        "tools/emit_intelligence_superiority_board.py` and commit the regenerated file."
    )


def test_committed_board_every_beat_or_meet_cell_is_self_assessed():
    board = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    for cat in board["categories"]:
        for score in cat["scores"]:
            if score["verdict"] in ("BEAT", "MEET"):
                assert score["assessment_basis"] == "self_assessed", (
                    f"{cat['category_id']}/{score['feature_id']} vs {score['competitor']} claims "
                    f"assessment_basis={score['assessment_basis']!r} — no cell in this dataset is "
                    f"externally certified yet, so this would need a real cert_ref"
                )
