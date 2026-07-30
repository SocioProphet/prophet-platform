"""Conformance: this implementation against the estate's shared vectors.

The vectors live in sourceos-spec (`conformance/lawful-verdict-vectors.json`) and are
consumed by every implementation on the mesh — this package and Noetica's TypeScript
`dispatch-ledger`. Two implementations that each pass their own unit tests can still
disagree with each other; only a shared vector set makes cross-language drift detectable,
which is the entire reason the file exists rather than each repo asserting its own table.

The vectors are VENDORED into `conformance/` with their upstream digests recorded in
`conformance/_provenance.json`, so the assertions that READ THE VENDORED ARTEFACTS -- the
vector suite, the sealed cross-language example, and the schema checks -- run
unconditionally and cannot skip.

That claim is scoped on purpose. Two tests in this file DO skip, and saying "these tests
can never skip" flatly would be false: `test_vendored_vectors_match_upstream` skips when
the real spec is unreachable (always, in CI), and the schema tests `importorskip`
jsonschema. The never-skip guarantee covers conformance against the vendored copy; it does
not cover freshness against upstream. Those are different properties and the difference is
the point.

Vendoring is deliberate: prophet-platform (SocioProphet) and sourceos-spec (SourceOS-Linux)
are in different orgs, so CI's GITHUB_TOKEN cannot check the spec out — the first version of
this suite duly reported UNVERIFIED and failed the build. A conformance gate that depends on
network access it does not have is not a gate.

Drift is caught separately. When the real spec IS present — a dev tree, or CI with cross-org
access — `test_vendored_vectors_match_upstream` asserts the vendored bytes still hash to the
recorded digests. So: non-skipping conformance against the vendored copy, drift detection
wherever it is actually possible, and an honest line between the two rather than one claim
covering both.
"""

from __future__ import annotations

import hashlib
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
from lawful_verdict import _seal  # forging tests must re-seal, as a real forger would

VERDICTS = ["NEG", "ZERO", "POS"]

#: The vendored copies. Always present, so nothing here can skip for want of a file.
VENDORED = Path(__file__).resolve().parents[1] / "conformance"


def _upstream_roots() -> list[Path]:
    """Where the real sourceos-spec might be, for the DRIFT check only. SOURCEOS_SPEC_DIR is
    authoritative when set — no fallback, so a stray local checkout cannot make a
    misconfigured CI run look like it verified something."""
    env = os.environ.get("SOURCEOS_SPEC_DIR")
    if env:
        return [Path(env)]
    return [
        Path(__file__).resolve().parents[5] / "sourceos-spec",   # dev tree sibling
        Path.home() / "dev" / "sourceos-spec",
    ]


def _vendored(name: str) -> Path:
    p = VENDORED / name
    assert p.exists(), (
        f"vendored conformance file missing: {p}. These are committed on purpose — see "
        f"conformance/_provenance.json. Their absence is a packaging bug, never a reason to skip."
    )
    return p


def _vectors() -> dict:
    return json.loads(_vendored("lawful-verdict-vectors.json").read_text(encoding="utf-8"))


def test_vendored_vectors_match_upstream() -> None:
    """The drift check. Vendoring buys availability; only this buys freshness.

    This is the ONLY check in the suite that compares the vendored bytes to anything
    outside this directory, and it SKIPS in CI (cross-org token — the spec lives in
    SourceOS-Linux, this repo in SocioProphet).

    The consequence is worth stating plainly rather than leaving implied. The workflow's
    digest step compares each vendored file to a digest recorded in _provenance.json,
    which sits in the same directory and is editable in the same commit. Measured:

        tamper a vector only            -> digest step RED
        tamper a vector AND its digest  -> digest step GREEN, suite 21 passed / 1 skipped

    So in CI a co-edited vector is undetectable and the run is fully green. That is a real
    residual, not a solved problem. Do not read a green run here as "agrees with the spec";
    read it as "self-consistent with the vendored copy". Closing it needs cross-org read
    access so this test can run in CI.
    """
    prov = json.loads(_vendored("_provenance.json").read_text(encoding="utf-8"))
    roots = _upstream_roots()
    # Require EVERY provenance path, not just the vectors. Selecting a root on the
    # strength of one file present, then reading three, turns an incomplete dev
    # checkout into a FileNotFoundError stacktrace where the intended outcome is the
    # explicit "UNVERIFIED" skip. Copilot caught this.
    def _complete(r: Path) -> bool:
        return all((r / m["sourcePath"]).exists() for m in prov["files"].values())
    root = next((r for r in roots if _complete(r)), None)
    if root is None:
        _unavailable("a COMPLETE upstream sourceos-spec (vendored-copy drift check)", roots)
        return
    stale: list[str] = []
    for name, meta in prov["files"].items():
        upstream = root / meta["sourcePath"]
        digest = "sha256:" + hashlib.sha256(upstream.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            stale.append(f"{name}: vendored {meta['sha256'][:20]}… upstream {digest[:20]}…")
        assert hashlib.sha256(_vendored(name).read_bytes()).hexdigest() == digest.split(":")[1], \
            f"{name}: vendored BYTES differ from upstream — re-vendor"
    assert not stale, "vendored conformance artefacts are stale:\n  " + "\n  ".join(stale)


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
    example = json.loads(_vendored("lawful-dispatch-receipt.example.json").read_text(encoding="utf-8"))
    recorded = example["seal"].pop("attestation")
    recomputed = "sha256:" + hashlib.sha256(canonical_json(example).encode()).hexdigest()
    assert recomputed == recorded, "canonical-JSON seal disagrees across languages"


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
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(
        json.loads(_vendored("LawfulDispatchReceipt.json").read_text(encoding="utf-8")))
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


# ── the SEAL functions themselves, pinned by vectors ────────────────────────────
# These exist because two real divergences got past everything else. The schema only checks
# that a digest is well-formed, and a WRONG digest is still well-formed — so nothing in the
# receipt-shaped tests could detect that the digest function disagreed across languages.

def test_canonical_json_matches_the_shared_vectors_including_non_ascii() -> None:
    """The ensure_ascii trap. Python's default escapes "café" to "caf\\u00e9" while
    JavaScript emits it raw, so with the default every seal over non-ASCII content diverges.
    The cross-language seal test passed anyway, because the spec's example receipt is pure
    ASCII — which is exactly why the function needs vectors of its own."""
    cases = _vectors()["canonicalJson"]["cases"]
    assert any(any(ord(ch) > 127 for ch in json.dumps(c["input"], ensure_ascii=False)) for c in cases), \
        "vectors must include a non-ASCII case or this test cannot catch the trap"
    for c in cases:
        got = canonical_json(c["input"])
        assert got == c["expected"], f"{c.get('why', '')}: expected {c['expected']!r}, got {got!r}"


def test_content_hash_matches_the_shared_vectors() -> None:
    """contentHash(s) = sha256(canonicalJson(s)) — over the QUOTED JSON encoding, not the raw
    bytes. An earlier version here hashed text.encode() directly and disagreed with
    TypeScript on every single input."""
    for c in _vectors()["contentHash"]["cases"]:
        got = content_hash(c["input"])
        assert got == c["expected"], f"{c.get('why', '')}: input {c['input']!r} → {got}, want {c['expected']}"


def test_a_receipt_with_non_ascii_content_still_seals_reproducibly() -> None:
    """End to end: the bug's real consequence was a receipt that would not verify in another
    language the moment it carried an accented character."""
    ev = EvidenceFactor(request_hash=content_hash("qué es la capital de España?"),
                        answer_hash=content_hash("Madrid — 中文 🔒"), grounded=True)
    r = Receipt("urn:srcos:dispatch:x", "2026-07-29T00:00:00Z", _law(), ev, 0, "genesis")
    assert r.attestation() == r.attestation(), "deterministic"
    body = r.body()
    assert "\\u" not in canonical_json(body), "the canonical form must carry raw non-ASCII, not escapes"


def test_truth_product_raises_a_useful_error_not_a_bare_KeyError() -> None:
    # A bare KeyError from a primitive used in tamper-evidence checking tells a caller
    # nothing. The most likely cause is a legacy row with no factors, and the message says so.
    for law, ev in [(None, "POS"), ("POS", None), (None, None), ("MAYBE", "POS")]:
        with pytest.raises(ValueError, match="not a verdict"):
            truth_product(law, ev)  # type: ignore[arg-type]
    assert truth_product("POS", "POS") == "POS", "and still works on real input"


# ── Copilot (suppressed, low-confidence — but correct): replay() must fail closed ──
#
# These were not inline comments; they were folded into a "Comments suppressed due to
# low confidence" block on the review body, which /pulls/N/comments does not return.
# Both were right.
#
# replay() exists to validate a ledger that may have been tampered with. Its contract is
# (ok, validated_count, reason). Before this, a malformed entry produced a KeyError or
# TypeError instead — a crash where the contract promised a verdict.


def _sealed_ledger() -> DispatchLedger:
    led = DispatchLedger()
    led.append("urn:srcos:dispatch:0", "2026-07-29T00:00:00Z", _law(),
               EvidenceFactor(request_hash=content_hash("q"), answer_hash=content_hash("a"),
                              grounded=True),
               emitter="test")
    ok, n, reason = led.replay()
    assert ok and n == 1, f"fixture must start valid: {reason}"
    return led


def _reseal(e: dict) -> None:
    """Re-seal an entry after damaging it, exactly as a capable forger would.

    Load-bearing, not ceremony. The first version of the test below damaged the entry
    and stopped there — but a structural edit changes the sealed body, so the
    attestation check caught every case BEFORE execution ever reached the malformed
    field. The tests passed while exercising the wrong branch entirely: with the
    exception handler narrowed to a type that never fires, all of them stayed green.
    Re-sealing is what forces replay() past the hash check and into the code path the
    fail-closed boundary actually protects.
    """
    body = {k: v for k, v in e.items() if k != "seal"}
    body["seal"] = {"seq": e["seal"]["seq"], "prev": e["seal"]["prev"]}
    e["seal"]["attestation"] = _seal(body)


@pytest.mark.parametrize("damage,label", [
    (lambda e: e.pop("law"),                            "missing law"),
    (lambda e: e.pop("evidence"),                       "missing evidence"),
    (lambda e: e.pop("verdict"),                        "missing verdict"),
    (lambda e: e.pop("evidenceTier"),                   "missing evidenceTier"),
    (lambda e: e["law"].pop("factor"),                  "missing law.factor"),
    (lambda e: e["law"].pop("source"),                  "missing law.source"),
    (lambda e: e.__setitem__("law", "not a mapping"),   "law is a string"),
    (lambda e: e.__setitem__("law", None),              "law is null"),
    (lambda e: e["law"].__setitem__("factor", "MAYBE"), "unknown factor value"),
    (lambda e: e["law"].__setitem__("factor", None),    "null factor (legacy row)"),
])
def test_replay_returns_a_finding_rather_than_raising(damage, label) -> None:
    """The forger is maximally capable: they damage the entry AND re-seal, so the chain
    verifies and only replay()'s own robustness stands between them and a crash."""
    led = _sealed_ledger()
    damage(led.entries[0])
    _reseal(led.entries[0])
    ok, i, reason = led.replay()          # must not raise
    assert ok is False, f"{label}: replay ACCEPTED a malformed entry"
    assert i == 0 and reason, f"{label}: no reason given"


def test_the_malformed_entry_tests_really_reach_the_fail_closed_path() -> None:
    """Guards the guard. If _reseal ever stopped working, the cases above would go back
    to being caught by the attestation check and would silently stop testing anything.
    Here the reason must NOT be an attestation mismatch."""
    led = _sealed_ledger()
    led.entries[0]["law"].pop("factor")
    _reseal(led.entries[0])
    ok, _, reason = led.replay()
    assert ok is False
    assert "attestation" not in (reason or ""), (
        f"still being caught by the hash check, not the malformed-entry path: {reason}")
    assert "malformed entry" in (reason or ""), f"unexpected reason: {reason}"


def test_replay_rejects_an_evidence_tier_outside_the_vocabulary() -> None:
    """Copilot: "can let invalid tiers like T0 pass as OK". Correct — the old check only
    rejected T1-where-T2-is-owed, so any UNRECOGNISED tier validated. A forger who cannot
    over-claim T1 could instead write a tier nothing understands.

    The forger here is maximally capable: they edit the field AND re-seal, so the hash
    chain verifies and only the semantic check can catch it.
    """
    for bogus in ("T0", "T3", "", "t1", 1, None):
        led = _sealed_ledger()
        e = led.entries[0]
        e["evidenceTier"] = bogus
        body = {k: v for k, v in e.items() if k != "seal"}
        body["seal"] = {"seq": e["seal"]["seq"], "prev": e["seal"]["prev"]}
        e["seal"]["attestation"] = _seal(body)      # re-seal: the chain now verifies
        ok, i, reason = led.replay()
        assert ok is False, f"tier {bogus!r} was ACCEPTED"
        assert "evidenceTier" in (reason or ""), f"tier {bogus!r}: wrong reason {reason!r}"


def test_replay_still_allows_honest_under_claiming() -> None:
    """T2 where T1 was earned is deliberately legal — the fix must not turn conservatism
    into a violation."""
    led = _sealed_ledger()
    e = led.entries[0]
    assert e["evidenceTier"] == "T1", "fixture should have earned T1"
    e["evidenceTier"] = "T2"
    body = {k: v for k, v in e.items() if k != "seal"}
    body["seal"] = {"seq": e["seal"]["seq"], "prev": e["seal"]["prev"]}
    e["seal"]["attestation"] = _seal(body)
    ok, _, reason = led.replay()
    assert ok, f"under-claiming must remain valid, got: {reason}"


def test_an_incomplete_spec_checkout_skips_rather_than_stacktraces(tmp_path, monkeypatch) -> None:
    """Copilot: the root was chosen because the VECTORS existed, then all three
    provenance paths were read — so a checkout with vectors but no schemas/ raised
    FileNotFoundError instead of reporting UNVERIFIED."""
    partial = tmp_path / "sourceos-spec"
    (partial / "conformance").mkdir(parents=True)
    (partial / "conformance" / "lawful-verdict-vectors.json").write_bytes(b"{}")
    monkeypatch.setenv("SOURCEOS_SPEC_DIR", str(partial))
    # Skipped derives from BaseException, NOT Exception. The first version of this test
    # used pytest.raises(Exception), so the Skipped propagated straight through and
    # skipped THIS test — which then reported as a skip and asserted nothing at all.
    # A test that cannot fail, arrived at by testing a skip. Catch the real type.
    from _pytest.outcomes import Skipped
    with pytest.raises(Skipped) as exc:
        test_vendored_vectors_match_upstream()
    assert "UNVERIFIED" in str(exc.value), f"wrong skip reason: {exc.value}"
    assert "COMPLETE" in str(exc.value), "must name incompleteness as the cause"


def test_replay_reason_does_not_echo_unbounded_attacker_text() -> None:
    """Copilot: `reason` embedded str(exc) verbatim, and the entry is untrusted — so a
    forger could push arbitrary volume into whatever consumes the reason."""
    led = _sealed_ledger()
    e = led.entries[0]
    e["law"] = {"factor": "X" * 100_000, "source": "measured"}
    _reseal(e)
    ok, _, reason = led.replay()
    assert ok is False
    assert len(reason) < 1_000, f"reason is {len(reason)} chars — unbounded attacker text"
    assert "chars)" in reason, "truncation must be visible, not silent"
