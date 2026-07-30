"""Conformance: this implementation against the estate's shared vectors.

The vectors live in sourceos-spec (`conformance/lawful-verdict-vectors.json`) and are
consumed by every implementation on the mesh — this package and Noetica's TypeScript
`dispatch-ledger`. Two implementations that each pass their own unit tests can still
disagree with each other; only a shared vector set makes cross-language drift detectable,
which is the entire reason the file exists rather than each repo asserting its own table.

If sourceos-spec is not checked out beside this repo the vector tests SKIP with a loud
reason locally, and FAIL in CI, where the workflow sets LAWFUL_VERDICT_REQUIRE_VECTORS=1.
They must never silently pass: a conformance suite reporting green when it never loaded the
vectors converts an unknown into a false assurance, which is the same defect class as the
asserted verdict this contract exists to eliminate. Verified in both directions — with the
vectors moved aside, the strict run fails 5 tests and the permissive run skips 5.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

#: In CI the vectors MUST be present. A conformance suite that reports green because it
#: never loaded the vectors converts an unknown into a false assurance — the precise defect
#: this contract exists to prevent. Locally a skip is a developer convenience; with
#: LAWFUL_VERDICT_REQUIRE_VECTORS=1 it becomes a hard failure.
REQUIRE = os.environ.get("LAWFUL_VERDICT_REQUIRE_VECTORS") == "1"


def _unavailable(what: str, looked: list[Path]) -> None:
    msg = (f"{what} not found — cross-language agreement is UNVERIFIED. "
           f"Looked in: {', '.join(str(p) for p in looked)}")
    if REQUIRE:
        raise AssertionError("LAWFUL_VERDICT_REQUIRE_VECTORS=1 but " + msg)
    pytest.skip(msg)

from lawful_verdict import (
    DispatchLedger, EvidenceFactor, LawFactor, Receipt, canonical_json, content_hash,
    evidence_tier, evidence_verdict, law_verdict, truth_product,
)

VERDICTS = ["NEG", "ZERO", "POS"]

def _spec_roots() -> list[Path]:
    """Where sourceos-spec might be. SOURCEOS_SPEC_DIR comes first because CI cannot use a
    sibling directory: actions/checkout refuses paths outside $GITHUB_WORKSPACE, so the
    workflow checks the spec out into a subdirectory and points at it explicitly."""
    env = os.environ.get("SOURCEOS_SPEC_DIR")
    if env:
        # AUTHORITATIVE when set: no fallback. An explicitly configured spec directory that
        # does not contain the vectors is a misconfiguration, and falling back to a stray
        # local checkout would let CI report agreement with a file it was not asked to read.
        return [Path(env)]
    return [
        Path(__file__).resolve().parents[5] / "sourceos-spec",   # dev tree sibling
        Path.home() / "dev" / "sourceos-spec",
    ]


def _spec_file(*parts: str) -> tuple[Path | None, list[Path]]:
    looked = [r.joinpath(*parts) for r in _spec_roots()]
    return next((p for p in looked if p.exists()), None), looked


_CANDIDATES = [r / "conformance" / "lawful-verdict-vectors.json" for r in _spec_roots()]


def _vectors() -> dict:
    found, looked = _spec_file("conformance", "lawful-verdict-vectors.json")
    if found:
        return json.loads(found.read_text(encoding="utf-8"))
    _unavailable("sourceos-spec conformance vectors", looked)
    raise AssertionError("unreachable")


# ── the shared vectors ──────────────────────────────────────────────────────────

def test_product_table_matches_the_shared_vectors() -> None:
    v = _vectors()
    table = v["product"]["table"]
    assert len(table) == 9, "the product is total on a 3-element chain: 9 cells, no gaps"
    for row in table:
        assert truth_product(row["law"], row["evidence"]) == row["verdict"], row


def test_the_sign_multiplication_trap_is_pinned_by_the_vectors() -> None:
    # The single cell that distinguishes a defensible product from a catastrophic one.
    v = _vectors()
    must_not = v["product"]["mustNotHold"]
    assert must_not, "the vectors must carry at least the NEG × NEG = POS counter-case"
    for bad in must_not:
        assert truth_product(bad["law"], bad["evidence"]) != bad["verdict"], bad


def test_law_factor_matches_the_shared_vectors() -> None:
    for row in _vectors()["lawFactor"]:
        got = law_verdict(row["barCleared"], row["residual"])
        assert got == row["expect"], f"{row['why']}: got {got}"


def test_evidence_factor_matches_the_shared_vectors() -> None:
    for row in _vectors()["evidenceFactor"]:
        got = evidence_verdict(row["requestHash"], row["answerHash"], row["grounded"],
                               row.get("refuted", False))
        assert got == row["expect"], f"{row['why']}: got {got}"


def test_tier_matches_the_shared_vectors() -> None:
    for row in _vectors()["tier"]:
        got = evidence_tier(row["lawSource"], row["evidenceSource"])
        assert got == row["expect"], f"{row['why']}: got {got}"


def test_the_sealed_example_in_the_spec_verifies_against_this_implementation() -> None:
    """The cross-language seal test. If Python's canonical JSON disagrees with the
    TypeScript canonicaliser by so much as key order or whitespace, this fails — which is
    exactly what we want it to catch, since a receipt sealed by one service must verify in
    another."""
    found, looked = _spec_file("examples", "lawful-dispatch-receipt.example.json")
    if found:
        example = json.loads(found.read_text(encoding="utf-8"))
        recorded = example["seal"].pop("attestation")
        import hashlib
        recomputed = "sha256:" + hashlib.sha256(canonical_json(example).encode()).hexdigest()
        assert recomputed == recorded, "canonical-JSON seal disagrees across languages"
        return
    _unavailable("sourceos-spec example receipt (seal agreement)", looked)


# ── the algebra, independent of the vector file ─────────────────────────────────

def test_product_is_the_lattice_meet_not_the_sign_product() -> None:
    sign = {"NEG": -1, "ZERO": 0, "POS": 1}
    assert sign["NEG"] * sign["NEG"] == 1, "sign arithmetic would say +1 (POS)"
    assert truth_product("NEG", "NEG") == "NEG", "the meet says NEG — the only sound answer"


def test_product_is_commutative_associative_with_POS_identity_and_NEG_absorbing() -> None:
    for a in VERDICTS:
        assert truth_product(a, "POS") == a, "POS is the identity: evidence alone adds nothing"
        assert truth_product(a, "NEG") == "NEG", "NEG absorbs: one refutation is enough"
        for b in VERDICTS:
            assert truth_product(a, b) == truth_product(b, a)
            for c in VERDICTS:
                assert truth_product(truth_product(a, b), c) == truth_product(a, truth_product(b, c))


def test_the_three_load_bearing_cells() -> None:
    assert truth_product("POS", "ZERO") == "ZERO", "lawful but unevidenced: a claim we decline to make"
    assert truth_product("ZERO", "POS") == "ZERO", "evidenced while carrying undischarged constraints"
    assert truth_product("NEG", "ZERO") == "NEG", "a refusal stands without corroboration"


# ── receipts and the ledger ─────────────────────────────────────────────────────

def _law(**kw) -> LawFactor:
    return LawFactor(**{"bar_cleared": True, "residual": (), **kw})


def _ev(**kw) -> EvidenceFactor:
    return EvidenceFactor(**{"request_hash": content_hash("q"), "answer_hash": content_hash("a"),
                             "grounded": True, **kw})


def test_a_receipt_cannot_assert_its_verdict_or_tier() -> None:
    # Both are derived properties. There is no constructor parameter for either, which is
    # the fix for the defect that started this: a caller-supplied verdict field that every
    # call site filled with the literal 'POS'.
    assert not hasattr(Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(), _ev(), 0, "genesis"), "_verdict")
    r = Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(), _ev(), 0, "genesis")
    assert r.verdict == "POS"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(residual=("citation.resolves",)), _ev(), 0, "genesis").verdict == "ZERO"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(bar_cleared=False), _ev(), 0, "genesis").verdict == "NEG"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(), _ev(refuted=True), 0, "genesis").verdict == "NEG"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(), _ev(grounded=False), 0, "genesis").verdict == "ZERO"


def test_a_declared_factor_forces_T2() -> None:
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(), _ev(), 0, "genesis").evidence_tier == "T1"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(source="declared"), _ev(), 0, "genesis").evidence_tier == "T2"
    assert Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z",
                   _law(), _ev(source="declared"), 0, "genesis").evidence_tier == "T2"


def test_evidence_tier_is_inside_the_seal() -> None:
    """T1 asserts the verdict was instrumented, so flipping it must break the attestation.
    Excluding it from the seal would leave the governance claim editable at rest."""
    measured = Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(), _ev(), 0, "genesis")
    declared = Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(source="declared"), _ev(), 0, "genesis")
    assert measured.evidence_tier != declared.evidence_tier
    assert measured.attestation() != declared.attestation(), "tier must be sealed"


def test_ledger_replays_clean_and_chains() -> None:
    led = DispatchLedger()
    for i in range(5):
        led.append(f"urn:srcos:dispatch:{i}", "2026-07-29T00:00:00Z", _law(),
                   _ev(request_hash=content_hash(f"q{i}"), answer_hash=content_hash(f"a{i}")),
                   emitter="prophet-workspace/drive")
    ok, count, reason = led.replay()
    assert (ok, count, reason) == (True, 5, None)
    assert led.entries[0]["seal"]["prev"] == "genesis"
    for i in range(1, 5):
        assert led.entries[i]["seal"]["prev"] == led.entries[i - 1]["seal"]["attestation"]


def test_tampering_makes_the_suffix_unreachable() -> None:
    led = DispatchLedger()
    for i in range(4):
        led.append(f"urn:srcos:dispatch:{i}", "2026-07-29T00:00:00Z", _law(),
                   _ev(request_hash=content_hash(f"q{i}")))
    assert led.replay()[0] is True

    # Alter content and DO NOT re-seal: caught by the attestation.
    led.entries[1]["evidence"]["grounded"] = False
    ok, count, reason = led.replay()
    assert ok is False
    assert "attestation mismatch" in reason or "does not follow" in reason


def test_a_resealed_forgery_is_still_caught_by_the_product() -> None:
    """The test that proves the product check is not redundant with the hash chain. The
    forger is maximally capable: they edit the verdict, re-seal so the chain verifies, and
    place the entry last so no prev-link is disturbed. Only re-deriving Law × Evidence
    catches it."""
    import hashlib
    led = DispatchLedger()
    led.append("urn:srcos:dispatch:0", "2026-07-29T00:00:00Z",
               _law(residual=("citation.resolves",)), _ev())
    assert led.entries[0]["verdict"] == "ZERO", "honestly ZERO: undischarged residual"

    e = led.entries[0]
    e["verdict"] = "POS"
    body = {k: v for k, v in e.items() if k != "seal"}
    body["seal"] = {"seq": e["seal"]["seq"], "prev": e["seal"]["prev"]}
    e["seal"]["attestation"] = "sha256:" + hashlib.sha256(canonical_json(body).encode()).hexdigest()

    ok, _, reason = led.replay()
    assert ok is False, "a verdict that does not follow from its factors is not evidence"
    assert "does not follow from ZERO × POS = ZERO" in reason


def test_a_forged_tier_upgrade_is_caught() -> None:
    import hashlib
    led = DispatchLedger()
    led.append("urn:srcos:dispatch:0", "2026-07-29T00:00:00Z", _law(source="declared"), _ev())
    assert led.entries[0]["evidenceTier"] == "T2"

    e = led.entries[0]
    e["evidenceTier"] = "T1"
    body = {k: v for k, v in e.items() if k != "seal"}
    body["seal"] = {"seq": e["seal"]["seq"], "prev": e["seal"]["prev"]}
    e["seal"]["attestation"] = "sha256:" + hashlib.sha256(canonical_json(body).encode()).hexdigest()

    ok, _, reason = led.replay()
    assert ok is False, "T1 on a declared factor must be rejected even when re-sealed"
    assert "claims T1 on a declared factor" in reason


def test_receipts_validate_against_the_spec_schema_if_available() -> None:
    """Emit every one of the 9 product cells and validate each against the contract. This
    is the end-to-end claim: what this library produces is what the estate's schema
    accepts, for every reachable verdict — not just the happy path."""
    found, looked = _spec_file("schemas", "LawfulDispatchReceipt.json")
    if found:
        if True:
            jsonschema = pytest.importorskip("jsonschema")
            validator = jsonschema.Draft202012Validator(json.loads(found.read_text(encoding="utf-8")))
            seen: set[str] = set()
            cases = [
                (_law(), _ev()),                                        # POS × POS
                (_law(), _ev(grounded=False)),                          # POS × ZERO
                (_law(), _ev(refuted=True)),                            # POS × NEG
                (_law(residual=("r",)), _ev()),                         # ZERO × POS
                (_law(residual=("r",)), _ev(grounded=False)),           # ZERO × ZERO
                (_law(residual=("r",)), _ev(refuted=True)),             # ZERO × NEG
                (_law(bar_cleared=False), _ev()),                       # NEG × POS
                (_law(bar_cleared=False), _ev(grounded=False)),         # NEG × ZERO
                (_law(bar_cleared=False), _ev(refuted=True)),           # NEG × NEG
            ]
            for law, ev in cases:
                r = Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", law, ev, 0, "genesis",
                            emitter="prophet-platform/libs/lawful-verdict")
                errs = list(validator.iter_errors(r.to_json()))
                assert not errs, f"{law.factor} × {ev.factor}: {errs[0].message if errs else ''}"
                seen.add(f"{law.factor}x{ev.factor}")
            assert len(seen) == 9, f"all 9 cells must be emitted and accepted, got {sorted(seen)}"
            return
    _unavailable("sourceos-spec LawfulDispatchReceipt schema", looked)
