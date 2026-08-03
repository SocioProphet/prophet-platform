"""Teeth for the CK/CM PROOF + TRUST layer (tools/recipe_proof.py).

The keystone that turns a runnable recipe into a portable, reproducible, citable
PROOF with a trust attestation — the Collective-Knowledge parity/beat. Proven BOTH
ways (a control that never fires is worse than none):

  POSITIVE:
    1. an assembled RecipeProof VERIFIES (soft recipe_ref, no register);
    2. the committed self-contained example VERIFIES standalone;
    3. with the register supplied, recipe_ref HARD-resolves.

  NEGATIVE (each REJECTED, fail-closed):
    4. a TAMPERED receipt (mutated ledger) breaks the chain;
    5. a receipt_ref that is absent from the ledger (missing receipt);
    6. metric DRIFT beyond epsilon (assembled with an injected observation);
    7. a FAILED division gate (CLOSED submission missing the clean-eval cert);
    8. an UNRESOLVABLE recipe_ref (id absent from a supplied register);
    9. a recipe_ref content-DIGEST mismatch against the register;
   10. a CLOSED-division proof missing a required field (no fixed task manifest);
   11. a LYING trust attestation (asserts clean_eval while the cert is contaminated).

Everything is CONSUMED: reproduce_bench emits the receipt/ledger, validate_submission
supplies the division + trust gates. Nothing here re-implements a gate.
SHA-256 is the FIPS 180-4 algorithm via stdlib hashlib, NOT a FIPS 140 module.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "eval" / "examples" / "recipe-proof"
FIXTURES = ROOT / "tests" / "platform_stubs" / "fixtures"
REGISTER = FIXTURES / "crystal-atlas-register.fixture.json"


def _rp():
    path = ROOT / "tools" / "recipe_proof.py"
    spec = importlib.util.spec_from_file_location("recipe_proof", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _submission() -> dict:
    return json.loads((EXAMPLES / "submission.closed.example.json").read_text())


def _assemble(rp, tmp_path, **overrides):
    """Assemble a proof into an isolated ledger under tmp_path (so tests never
    write to the committed example ledger). We point reproduce_bench's LEDGER_ROOT
    at tmp_path via monkeypatching the module the tool imports."""
    kwargs = dict(
        bench="isota", run_id="opus-class-r1", recipe_id="internal-model:isota-tournament",
        division="CLOSED", submission=_submission(),
    )
    kwargs.update(overrides)
    return rp.assemble(**kwargs)


@pytest.fixture()
def isolated_ledger(monkeypatch, tmp_path):
    """Redirect reproduce_bench's ledger root into tmp so assemble is hermetic."""
    rp = _rp()
    rb = rp._reproduce_bench()
    monkeypatch.setattr(rb, "LEDGER_ROOT", tmp_path / "reproduce")
    # recipe_proof resolves ledger_path relative to ROOT; keep paths ROOT-relative
    # by making the tmp ledger live under ROOT/build (gitignored) is unnecessary —
    # instead we verify via the returned proof after fixing ledger_path to absolute.
    return rp, rb, tmp_path


def _verify_assembled(rp, rb, proof, **verify_kwargs):
    """Verify a freshly-assembled proof whose ledger lives outside ROOT: rewrite
    ledger_path to an absolute path and point the tool's ROOT-join at it."""
    ledger_abs = rb.ledger_path_for(proof["bench"])
    # make ledger_path absolute so ROOT/ledger_path == ledger_abs
    proof = copy.deepcopy(proof)
    proof["repro_ledger_ref"]["ledger_path"] = str(ledger_abs)
    monkey_root = rp.ROOT
    # ROOT / absolute_path == absolute_path in pathlib, so no monkeypatch needed.
    assert (monkey_root / ledger_abs) == ledger_abs
    return rp.verify(proof, **verify_kwargs), proof


# ── POSITIVE ──────────────────────────────────────────────────────────────
def test_assembled_proof_verifies_soft(isolated_ledger):
    rp, rb, _ = isolated_ledger
    proof = _assemble(rp, None)
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is True, verdict.to_dict()


def test_committed_example_verifies_standalone():
    rp = _rp()
    proof = json.loads((EXAMPLES / "recipe-proof.example.json").read_text())
    assert rp.verify(proof).verified is True


def test_recipe_ref_hard_resolves_with_register():
    rp = _rp()
    proof = json.loads((EXAMPLES / "recipe-proof.example.json").read_text())
    verdict = rp.verify(proof, register_path=REGISTER)
    assert verdict.verified is True
    ref = {c.name: c for c in verdict.checks}["recipe_ref_resolvable"]
    assert ref.passed and "resolved" in ref.reason and "pending" not in ref.reason


# ── NEGATIVE ──────────────────────────────────────────────────────────────
def test_tampered_receipt_breaks_chain(isolated_ledger):
    rp, rb, _ = isolated_ledger
    proof = _assemble(rp, None)
    ledger = rb.ledger_path_for(proof["bench"])
    # tamper: flip the reproduce outcome in the persisted spine (chain must break).
    line = json.loads(ledger.read_text().splitlines()[-1])
    line["reproduce_outcome"]["observed"] = 999.0
    ledger.write_text(json.dumps(line, sort_keys=True) + "\n")
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "receipt_chain_intact" in verdict.failed()


def test_missing_receipt_ref_rejected(isolated_ledger):
    rp, rb, _ = isolated_ledger
    proof = _assemble(rp, None)
    proof = copy.deepcopy(proof)
    proof["receipt_ref"] = "0" * 64  # a receipt that is not on the ledger
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "receipt_chain_intact" in verdict.failed()


def test_metric_drift_beyond_epsilon_rejected(isolated_ledger):
    rp, rb, _ = isolated_ledger
    # inject a drifted observation: the deterministic arm must match EXACTLY, so
    # an injected 80.0 (vs recorded 88.79) makes the receipt's outcome fail.
    proof = _assemble(rp, None, inject=80.0)
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "metric_within_epsilon" in verdict.failed()


def test_failed_division_gate_rejected(isolated_ledger):
    rp, rb, _ = isolated_ledger
    sub = _submission()
    sub["clean_eval_certificate"] = None  # CLOSED requires a clean-eval cert
    proof = _assemble(rp, None, submission=sub)
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    # both the division verdict AND the trust attestation must catch this.
    assert "division_gates_pass" in verdict.failed()
    assert "trust_attestation_proven" in verdict.failed()


def test_unresolvable_recipe_ref_rejected():
    rp = _rp()
    proof = json.loads((EXAMPLES / "recipe-proof.example.json").read_text())
    proof = copy.deepcopy(proof)
    proof["recipe_ref"] = {"recipe_id": "internal-model:does-not-exist"}
    verdict = rp.verify(proof, register_path=REGISTER)
    assert verdict.verified is False
    assert "recipe_ref_resolvable" in verdict.failed()


def test_recipe_ref_digest_mismatch_rejected():
    rp = _rp()
    proof = json.loads((EXAMPLES / "recipe-proof.example.json").read_text())
    proof = copy.deepcopy(proof)
    proof["recipe_ref"] = {"recipe_id": "internal-model:isota-tournament", "content_digest": "a" * 64}
    verdict = rp.verify(proof, register_path=REGISTER)
    assert verdict.verified is False
    assert "recipe_ref_resolvable" in verdict.failed()


def test_closed_missing_required_field_rejected(isolated_ledger):
    rp, rb, _ = isolated_ledger
    sub = _submission()
    sub["task_manifest"] = {"unchanged": False}  # CLOSED requires a fixed manifest
    proof = _assemble(rp, None, submission=sub)
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "division_gates_pass" in verdict.failed()


def test_lying_trust_attestation_rejected(isolated_ledger):
    rp, rb, _ = isolated_ledger
    sub = _submission()
    sub["clean_eval_certificate"]["status"] = "contaminated"
    proof = _assemble(rp, None, submission=sub)
    # force the attestation to LIE (assert clean while the cert is contaminated).
    proof["trust_attestation"]["clean_eval"] = True
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "trust_attestation_proven" in verdict.failed()


def test_fabricated_headline_value_rejected(isolated_ledger):
    """RED-TEAM: a bounded-arm proof whose receipt chain is intact and whose
    reproduction PASSED, but whose PUBLISHED headline value is inflated away from
    the reproduced number — smuggled in by widening the proof-declared epsilon.
    The published headline must BE the reproduced value; the tolerance is taken
    from the receipt, not the proof, so this must be REJECTED."""
    rp, rb, _ = isolated_ledger
    proof = _assemble(rp, None, run_id="sampled-headline-r1")
    proof = copy.deepcopy(proof)
    # inflate the published headline far from the actual reproduced observed and
    # widen the proof-declared epsilon to try to cover the drift.
    proof["headline"]["value"] = proof["headline"]["value"] + 19.0
    proof["headline"]["epsilon"] = 100.0
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "metric_within_epsilon" in verdict.failed()


def test_headline_epsilon_must_match_receipt_tolerance(isolated_ledger):
    """RED-TEAM: even without changing the value, a proof cannot misrepresent the
    tolerance — the declared epsilon must equal the receipt's recorded tolerance."""
    rp, rb, _ = isolated_ledger
    proof = _assemble(rp, None, run_id="sampled-headline-r1")
    proof = copy.deepcopy(proof)
    proof["headline"]["epsilon"] = proof["headline"]["epsilon"] + 1.0  # != receipt tolerance
    verdict, _ = _verify_assembled(rp, rb, proof)
    assert verdict.verified is False
    assert "metric_within_epsilon" in verdict.failed()


def test_schema_invalid_proof_rejected():
    rp = _rp()
    verdict = rp.verify({"recipe_proof_id": "bad", "recipe_ref": {"recipe_id": "NOT-A-VALID-ID"}})
    assert verdict.verified is False
    assert "schema_valid" in verdict.failed()
