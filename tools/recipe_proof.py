#!/usr/bin/env python3
"""recipe_proof — the CK/CM PROOF + TRUST layer.

WHY. A runnable recipe is not yet a *proof*. MLCommons Collective Knowledge (CK/CM)
makes recipes portable; this layer goes one step further and makes a recipe execution
a **portable, reproducible, citable proof with a trust attestation** — the keystone
that lets the estate beat Collective Knowledge, not just MLPerf.

WHAT IT DOES. It BINDS a recipe execution to a verifiable RecipeProof
(schemas/eval/recipe-proof.schema.json) by CONSUMING the pieces that already exist:

  * tools/reproduce_bench.py (#1269)  — runs the recorded run, emits the
    SHA-256 hash-chained repro-ledger spine (the receipt), and the tolerance gate.
  * schemas/eval/repro-ledger-entry.schema.json — the ledger contract (not forked).
  * tools/validate_submission.py (#1271) + schemas/eval/division-rules.json —
    the open/closed division verdict and the trust gates (clean-eval,
    provider-neutrality, no-laundering).
  * the crystal-atlas internal-model register (PR #1287, OPEN) — REFERENCED by a
    soft recipe_ref (id + optional content digest). Until the register lands on
    main, recipe_ref resolution is deferred (pending_register); when a register is
    supplied, resolution is HARD (unresolvable id / digest mismatch -> REJECT).
  * the DataCite concept/version client (#1267) — an OPTIONAL doi_ref, referenced.

Two verbs:

    assemble   run the recipe via reproduce_bench, emit receipt + ledger, and
               assemble a schema-valid RecipeProof.
    verify     INDEPENDENTLY verify a RecipeProof: chain intact + metric within
               epsilon + division gates pass + trust gates pass + recipe_ref
               resolvable. FAIL CLOSED on any broken condition.

Hashing note: SHA-256 is the FIPS 180-4 *algorithm* via Python's stdlib hashlib.
This is NOT a FIPS 140-validated cryptographic module. We describe it precisely.

License: MIT (matches repo LICENSE).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "eval"
RECIPE_PROOF_SCHEMA = SCHEMA_DIR / "recipe-proof.schema.json"

# Trust gates that a RecipeProof ALWAYS requires, independent of division.
TRUST_GATES = ("clean_eval_certificate", "provider_neutrality", "no_laundering")


# ---------------------------------------------------------------------------
# consume-not-fork: import the real reproduce_bench and validate_submission
# modules and CALL them. We never re-implement the ledger, the receipt chain,
# the tolerance gate, or the division/trust gates.
# ---------------------------------------------------------------------------
_MODULE_CACHE: dict[str, Any] = {}


def _load(module_name: str) -> Any:
    # Cache: load each consumed module once so a single process (and tests that
    # monkeypatch it) see one stable module object.
    if module_name in _MODULE_CACHE:
        return _MODULE_CACHE[module_name]
    path = ROOT / "tools" / (module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod  # dataclass field resolution needs registration
    spec.loader.exec_module(mod)
    _MODULE_CACHE[module_name] = mod
    return mod


def _reproduce_bench():
    return _load("reproduce_bench")


def _validate_submission():
    return _load("validate_submission")


def _proof_validator() -> Draft202012Validator:
    schema = json.loads(RECIPE_PROOF_SCHEMA.read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


# ---------------------------------------------------------------------------
# recipe_ref resolution against the crystal-atlas register (soft/hard).
# ---------------------------------------------------------------------------
RECIPE_ID_RE = __import__("re").compile(r"^internal-model:[a-z0-9-]+$")


def _load_register(register_path: Path) -> dict[str, dict]:
    """Return {model_id: entry} from a crystal-atlas internal-model register."""
    doc = json.loads(register_path.read_text())
    entries = doc.get("models") or doc.get("entries") or []
    return {e["model_id"]: e for e in entries if "model_id" in e}


def resolve_recipe_ref(recipe_ref: dict, register_path: Path | None) -> tuple[bool, str]:
    """Resolve a soft recipe_ref.

      * malformed recipe_id                          -> (False, "malformed")    HARD
      * no register available                        -> (True,  "pending_register") SOFT
      * register present, id absent                  -> (False, "unresolvable") HARD
      * register present, digest given but mismatch  -> (False, "digest_mismatch") HARD
      * register present, id resolves                -> (True,  "resolved")     HARD
    """
    recipe_id = recipe_ref.get("recipe_id", "")
    if not RECIPE_ID_RE.match(recipe_id):
        return False, "malformed"
    if register_path is None or not register_path.exists():
        # Coordination with crystal-atlas #1287: the register is not on main yet.
        # The reference is format-valid; binding activates when the register lands.
        return True, "pending_register"
    register = _load_register(register_path)
    entry = register.get(recipe_id)
    if entry is None:
        return False, "unresolvable"
    declared = recipe_ref.get("content_digest")
    if declared is not None:
        rb = _reproduce_bench()
        actual = rb.canonical_digest(entry)
        if declared != actual:
            return False, "digest_mismatch"
    return True, "resolved"


def register_entry_digest(recipe_id: str, register_path: Path) -> str:
    """Content-address a register entry (SHA-256 / FIPS 180-4 algorithm)."""
    entry = _load_register(register_path)[recipe_id]
    return _reproduce_bench().canonical_digest(entry)


# ---------------------------------------------------------------------------
# ASSEMBLE — run the recipe via reproduce_bench, then bind the proof.
# ---------------------------------------------------------------------------
def assemble(bench: str, run_id: str, recipe_id: str, division: str,
             submission: dict, register_path: Path | None = None,
             concept_doi: str | None = None, version_doi: str | None = None,
             proof_id: str | None = None, inject: float | None = None) -> dict:
    """Run the recorded run through reproduce_bench (emits the receipt + ledger),
    then assemble a schema-valid RecipeProof bound to that receipt."""
    rb = _reproduce_bench()
    record = rb.load_record(rb.record_path(bench, run_id))
    observed = rb.observe(record, override=inject)
    passed, detail = rb.reproduce_gate(record, observed)
    spine = rb.emit_ledger_entry(record, observed, passed, detail)
    if not rb.verify_ledger(rb.ledger_path_for(bench)):
        raise RuntimeError("repro-ledger chain verification FAILED at assemble time")

    ledger_path = rb.ledger_path_for(bench)
    recipe_ref: dict[str, Any] = {"recipe_id": recipe_id}
    if register_path is not None and register_path.exists():
        try:
            recipe_ref["content_digest"] = register_entry_digest(recipe_id, register_path)
        except KeyError:
            pass  # id absent — leave digest off; verify will mark it unresolvable

    headline: dict[str, Any] = {
        "metric_id": record["headline_metric_id"],
        "value": observed,
        "determinism_class": record["determinism"],
    }
    if record["determinism"] == "bounded_nondeterministic":
        headline["epsilon"] = float(record.get("epsilon", 0.0))

    proof: dict[str, Any] = {
        "recipe_proof_id": proof_id or ("rp.%s.%s" % (bench, run_id)),
        "recipe_ref": recipe_ref,
        "run_id": run_id,
        "bench": bench,
        "repro_ledger_ref": {
            # ROOT-relative when the ledger lives in-tree (the norm); absolute
            # otherwise (verify resolves ROOT/<path>, and ROOT/<abs> == <abs>).
            "ledger_path": (str(ledger_path.relative_to(ROOT))
                            if ledger_path.is_relative_to(ROOT) else str(ledger_path)),
            "repro_ledger_entry_id": spine["entry"]["repro_ledger_entry_id"],
        },
        "receipt_ref": spine["entry_digest"],
        "headline": headline,
        "division": division,
        "submission": submission,
        "trust_attestation": {
            "clean_eval": bool((submission.get("clean_eval_certificate") or {}).get("status") == "clean"),
            "provider_neutrality": (submission.get("provider_neutrality") or {}).get("provider_terms_in_scoring") is False,
            "no_laundering": True,
        },
    }
    if concept_doi or version_doi:
        proof["doi_ref"] = {k: v for k, v in (("concept_doi", concept_doi), ("version_doi", version_doi)) if v}

    _proof_validator().validate(proof)
    return proof


# ---------------------------------------------------------------------------
# VERIFY — independent, fail-closed verification of a RecipeProof.
# ---------------------------------------------------------------------------
@dataclass
class Check:
    name: str
    passed: bool
    reason: str


@dataclass
class ProofVerdict:
    recipe_proof_id: str
    verified: bool
    checks: list[Check] = field(default_factory=list)

    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_proof_id": self.recipe_proof_id,
            "verified": self.verified,
            "checks": [{"check": c.name, "passed": c.passed, "reason": c.reason} for c in self.checks],
            "failed_checks": self.failed(),
        }


def _find_spine(ledger_path: Path, receipt_ref: str) -> dict | None:
    if not ledger_path.exists():
        return None
    for ln in ledger_path.read_text().splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("entry_digest") == receipt_ref:
            return rec
    return None


def verify(proof: dict, register_path: Path | None = None,
           min_trials: int | None = None) -> ProofVerdict:
    """Independently verify a RecipeProof. FAIL CLOSED: every check must pass."""
    checks: list[Check] = []

    # 0. schema-valid (a malformed proof never silently passes).
    try:
        _proof_validator().validate(proof)
        checks.append(Check("schema_valid", True, "conforms to recipe-proof.schema.json"))
    except Exception as exc:  # jsonschema.ValidationError
        checks.append(Check("schema_valid", False, "schema violation: %s" % str(exc).splitlines()[0]))
        return ProofVerdict(proof.get("recipe_proof_id", "?"), False, checks)

    rb = _reproduce_bench()

    # 1. recipe_ref resolvable (soft when no register; hard when one is supplied).
    ok, status = resolve_recipe_ref(proof["recipe_ref"], register_path)
    checks.append(Check("recipe_ref_resolvable", ok, "recipe_ref %s" % status))

    # 2. receipt chain intact + receipt_ref present on the ledger.
    ledger_path = ROOT / proof["repro_ledger_ref"]["ledger_path"]
    chain_ok = rb.verify_ledger(ledger_path)
    spine = _find_spine(ledger_path, proof["receipt_ref"]) if chain_ok else None
    if not chain_ok:
        checks.append(Check("receipt_chain_intact", False, "repro-ledger chain broken/tampered (%s)" % ledger_path))
    elif spine is None:
        checks.append(Check("receipt_chain_intact", False, "receipt_ref not found on ledger (missing/tampered receipt)"))
    else:
        checks.append(Check("receipt_chain_intact", True, "hash-chain intact; receipt_ref present"))

    # 3. metric binds the receipt's reproduce outcome. The published headline MUST
    #    BE the value the receipt reproduced — no fabrication. We bind EXACTLY to
    #    the receipt's observed value and take the tolerance/rule/determinism FROM
    #    THE RECEIPT, never from proof-declared fields. (A proof-declared epsilon is
    #    attacker-controlled: widening it would let a fabricated headline that drifts
    #    far from the reproduced number slip through. The receipt is the ground truth.)
    if spine is None:
        checks.append(Check("metric_within_epsilon", False, "no receipt to bind the metric to"))
    else:
        outcome = spine.get("reproduce_outcome") or {}
        recorded_metric = outcome.get("headline_metric_id")
        det = proof["headline"]["determinism_class"]
        observed = float(outcome.get("observed", "nan"))
        value = float(proof["headline"]["value"])
        # the published headline value is exactly the reproduced value on the receipt.
        value_binds = (value == observed)  # NaN (external dispatch-only) never binds
        # the determinism class the proof claims must match how the receipt was gated.
        rule_expected = "exact" if det == "deterministic" else "within_epsilon"
        class_binds = (outcome.get("rule") == rule_expected)
        # for a bounded arm, the proof-declared epsilon must equal the receipt's
        # recorded tolerance — the proof cannot misrepresent the tolerance either.
        tol_binds = True
        if det == "bounded_nondeterministic":
            tol_binds = (float(proof["headline"].get("epsilon", 0.0)) == float(outcome.get("tolerance", -1.0)))
        metric_ok = bool(outcome.get("passed")) and value_binds and class_binds and tol_binds \
            and recorded_metric == proof["headline"]["metric_id"] \
            and spine.get("bench") == proof.get("bench") \
            and spine["entry"]["run_id"] == proof["run_id"]
        reason = ("headline binds the receipt (value=%g == observed, rule=%s)" % (value, outcome.get("rule"))
                  if metric_ok else
                  "metric does not bind the receipt (passed=%s value_binds=%s class_binds=%s tol_binds=%s metric=%s vs %s run=%s)"
                  % (outcome.get("passed"), value_binds, class_binds, tol_binds,
                     recorded_metric, proof["headline"]["metric_id"], proof["run_id"]))
        checks.append(Check("metric_within_epsilon", metric_ok, reason))

    # 4. division gates pass (#1271, over the embedded submission descriptor).
    vs = _validate_submission()
    sub = proof["submission"]
    div_ok = False
    div_reason = ""
    try:
        if sub.get("division") != proof["division"]:
            div_reason = "submission.division %r != proof.division %r" % (sub.get("division"), proof["division"])
        else:
            verdict = vs.validate_submission(sub, min_trials=min_trials)
            div_ok = verdict.valid
            div_reason = ("division %s VALID" % proof["division"]) if div_ok \
                else "division %s REJECTED: failed %s" % (proof["division"], verdict.failed_gates())
    except ValueError as exc:
        div_reason = "division rules error: %s" % exc
    checks.append(Check("division_gates_pass", div_ok, div_reason))

    # 5. trust attestation proven (clean-eval + provider-neutrality + no-laundering),
    #    ALWAYS required regardless of division. We PROVE the assertions by running
    #    the estate gates over the submission, not by trusting the flags.
    try:
        verdict = vs.validate_submission(sub, min_trials=min_trials)
        by_gate = {r.gate: r for r in verdict.results}
        trust_failed = [g for g in TRUST_GATES if not by_gate.get(g) or not by_gate[g].passed]
        # also require the proof's own asserted flags to be truthful.
        att = proof["trust_attestation"]
        lie = []
        if att.get("clean_eval") is not (by_gate.get("clean_eval_certificate") and by_gate["clean_eval_certificate"].passed):
            lie.append("clean_eval")
        if att.get("provider_neutrality") is not (by_gate.get("provider_neutrality") and by_gate["provider_neutrality"].passed):
            lie.append("provider_neutrality")
        if att.get("no_laundering") is not (by_gate.get("no_laundering") and by_gate["no_laundering"].passed):
            lie.append("no_laundering")
        trust_ok = not trust_failed and not lie
        reason = "clean-eval + provider-neutrality + no-laundering all proven" if trust_ok \
            else "trust gates failed=%s; attestation lies=%s" % (trust_failed, lie)
    except ValueError as exc:
        trust_ok = False
        reason = "trust gate error: %s" % exc
    checks.append(Check("trust_attestation_proven", trust_ok, reason))

    verified = all(c.passed for c in checks)
    return ProofVerdict(proof["recipe_proof_id"], verified, checks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_assemble(args: argparse.Namespace) -> int:
    submission = json.loads(Path(args.submission).read_text())
    register = Path(args.register) if args.register else None
    proof = assemble(
        bench=args.bench, run_id=args.run, recipe_id=args.recipe, division=args.division,
        submission=submission, register_path=register,
        concept_doi=args.concept_doi, version_doi=args.version_doi,
        proof_id=args.proof_id, inject=args.inject_observed,
    )
    out = json.dumps(proof, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out + "\n")
        print("wrote RecipeProof -> %s (receipt_ref=%s)" % (args.out, proof["receipt_ref"][:12]), file=sys.stderr)
    else:
        print(out)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        proof = json.loads(Path(args.proof).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print("malformed proof: %s" % exc, file=sys.stderr)
        return 2
    register = Path(args.register) if args.register else None
    verdict = verify(proof, register_path=register, min_trials=args.min_trials)
    print(json.dumps(verdict.to_dict(), indent=2))
    status = "VERIFIED" if verdict.verified else "REJECTED"
    print("\n%s: %s" % (status, verdict.recipe_proof_id)
          + ("" if verdict.verified else " — failed checks: %s" % verdict.failed()), file=sys.stderr)
    return 0 if verdict.verified else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CK/CM PROOF + TRUST layer: assemble and verify RecipeProofs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("assemble", help="run the recipe via reproduce_bench and assemble a RecipeProof")
    a.add_argument("--bench", required=True)
    a.add_argument("--run", required=True)
    a.add_argument("--recipe", required=True, help="crystal-atlas recipe id, e.g. internal-model:next-best-action")
    a.add_argument("--division", required=True, choices=["OPEN", "CLOSED"])
    a.add_argument("--submission", required=True, help="path to a validate_submission descriptor JSON")
    a.add_argument("--register", default=None, help="OPTIONAL crystal-atlas register JSON (hard-resolves recipe_ref)")
    a.add_argument("--concept-doi", default=None)
    a.add_argument("--version-doi", default=None)
    a.add_argument("--proof-id", default=None)
    a.add_argument("--out", default=None, help="write the proof here (default: stdout)")
    a.add_argument("--inject-observed", type=float, default=None,
                   help="TEETH: inject an observed headline (bypasses re-run) to prove the gate bites")
    a.set_defaults(func=_cmd_assemble)

    v = sub.add_parser("verify", help="independently verify a RecipeProof (fail-closed)")
    v.add_argument("proof", help="path to a RecipeProof JSON")
    v.add_argument("--register", default=None, help="OPTIONAL crystal-atlas register JSON (hard-resolves recipe_ref)")
    v.add_argument("--min-trials", type=int, default=None)
    v.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
