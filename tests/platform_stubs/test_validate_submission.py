"""Teeth for validate-submission — the single MLPerf-parity submission-validity check (Lever B).

Proven BOTH ways (controls that fire), grounded in issue #1263 feature 2:
  1. a COMPLIANT submission PASSES (CLOSED + OPEN);
  2. a submission missing the clean-eval certificate is REJECTED;
  3. a provider-neutrality violation is REJECTED;
  4. the OPEN division is genuinely more permissive than CLOSED (an
     OPEN-valid submission missing only the repro-ledger + fixed-manifest
     is REJECTED under CLOSED) — the division split is not vacuous;
  5. the submission descriptor + division rules validate against their schemas.
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


def _mod():
    path = ROOT / "tools" / "validate_submission.py"
    spec = importlib.util.spec_from_file_location("validate_submission", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod  # dataclass field resolution needs the module registered
    spec.loader.exec_module(mod)
    return mod


def _compliant_closed() -> dict:
    """A submission that passes every CLOSED gate."""
    return {
        "submission_id": "sub-001",
        "division": "CLOSED",
        "candidate_id": "cand.internal-runner",
        "benchmark_contract_id": "bc.sherlock.stage2",
        "governance": {"api": True, "rate": True, "auth": True, "cost": True, "observability": True},
        "provider_neutrality": {"scored_by": "internal_runner", "provider_terms_in_scoring": False},
        "metric_facts": [
            {"metric_definition_id": "md.isota.tournament_composite", "reproduced_by_us": True,
             "source_trust_class": "internal_reproduced", "is_headline": True, "trial_count": 30},
        ],
        "clean_eval_certificate": {"certificate_id": "ce-1", "status": "clean",
                                    "corpus_ref": "corpus://sherlock", "checked_at": "2026-08-03T00:00:00Z"},
        "repro_ledger_entry": {"repro_ledger_entry_id": "rl-1", "run_id": "run-1",
                                "environment_hash": "sha256:" + "e" * 64,
                                "methodology_snapshot_hash": "sha256:" + "f" * 64,
                                "seed_policy": "fixed:1729", "replay_artifact_id": "replay-1"},
        "task_manifest": {"unchanged": True, "declared_deviations": []},
        "minimum_trial_count": 30,
    }


# ── TEETH 1: compliant submissions PASS (both divisions) ──
def test_compliant_closed_passes():
    mod = _mod()
    verdict = mod.validate_submission(_compliant_closed())
    assert verdict.valid is True, verdict.to_dict()
    assert verdict.failed_gates() == []


def test_compliant_open_passes():
    mod = _mod()
    sub = _compliant_closed()
    sub["division"] = "OPEN"
    verdict = mod.validate_submission(sub)
    assert verdict.valid is True, verdict.to_dict()


# ── TEETH 2: missing clean-eval certificate is REJECTED ──
def test_missing_clean_eval_certificate_is_rejected():
    mod = _mod()
    for div in ("CLOSED", "OPEN"):
        sub = _compliant_closed()
        sub["division"] = div
        sub["clean_eval_certificate"] = None
        verdict = mod.validate_submission(sub)
        assert verdict.valid is False, div
        assert "clean_eval_certificate" in verdict.failed_gates(), div

    # a contaminated (non-clean) cert is also rejected — the control is not just "presence"
    sub = _compliant_closed()
    sub["clean_eval_certificate"]["status"] = "contaminated"
    assert mod.validate_submission(sub).valid is False


# ── TEETH 3: provider-neutrality violation is REJECTED ──
def test_provider_neutrality_violation_is_rejected():
    mod = _mod()
    # scored by provider-reported numbers
    sub = _compliant_closed()
    sub["provider_neutrality"] = {"scored_by": "provider_reported", "provider_terms_in_scoring": False}
    v1 = mod.validate_submission(sub)
    assert v1.valid is False and "provider_neutrality" in v1.failed_gates()

    # provider term leaked into scoring
    sub2 = _compliant_closed()
    sub2["provider_neutrality"] = {"scored_by": "internal_runner", "provider_terms_in_scoring": True}
    v2 = mod.validate_submission(sub2)
    assert v2.valid is False and "provider_neutrality" in v2.failed_gates()


# ── TEETH 3b: no-laundering — a cited (not-reproduced) headline is REJECTED ──
def test_laundered_cited_headline_is_rejected():
    mod = _mod()
    sub = _compliant_closed()
    sub["metric_facts"] = [
        {"metric_definition_id": "md.gpqa", "reproduced_by_us": False,
         "source_trust_class": "official_provider", "is_headline": True, "trial_count": 30},
    ]
    v = mod.validate_submission(sub)
    assert v.valid is False and "no_laundering" in v.failed_gates()


# ── TEETH 4: the OPEN/CLOSED split is not vacuous ──
def test_open_more_permissive_than_closed():
    mod = _mod()
    # drop the two CLOSED-only gates: repro-ledger + fixed task manifest
    sub = _compliant_closed()
    sub["repro_ledger_entry"] = None
    sub["task_manifest"] = {"unchanged": False, "declared_deviations": ["novel retrieval head"]}

    closed = copy.deepcopy(sub); closed["division"] = "CLOSED"
    open_ = copy.deepcopy(sub); open_["division"] = "OPEN"

    v_closed = mod.validate_submission(closed)
    v_open = mod.validate_submission(open_)
    assert v_closed.valid is False and set(v_closed.failed_gates()) >= {"repro_ledger_entry", "fixed_task_manifest"}
    assert v_open.valid is True, v_open.to_dict()


# ── TEETH 5: descriptor + rules validate against their schemas ──
def test_submission_and_rules_validate_against_schema():
    submission_schema = json.loads((SCHEMA_DIR / "submission.schema.json").read_text())
    jsonschema.validate(_compliant_closed(), submission_schema)

    rules = json.loads((SCHEMA_DIR / "division-rules.json").read_text())
    assert set(rules["divisions"]) == {"OPEN", "CLOSED"}
    # every required gate a division names must be implemented by the validator
    mod = _mod()
    implemented = set(mod.GATE_FUNCS) | {"minimum_trials_met"}
    for div, spec in rules["divisions"].items():
        for gate in spec["required_gates"]:
            assert gate in implemented, f"{div} requires unimplemented gate {gate}"
