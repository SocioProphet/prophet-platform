"""Truth = Law × Evidence — the estate's verdict algebra, for any Python service.

`×` is the MEET in the chain NEG < ZERO < POS: strong-Kleene conjunction, i.e. ``min``.
A three-element chain is a category, and the meet in a poset-as-category is the categorical
product, so the equation is an identity rather than a slogan — Truth is the terminal cone
over {Law, Evidence}.

It is emphatically NOT multiplication of signs in {-1, 0, +1}. That reading gives
``NEG × NEG = POS``: a gate that refused *and* an outcome that was refuted, certifying as
true. See :func:`truth_product` and the test that pins this cell.

The three cells that carry the product's whole value:

===============  ==================================================================
POS × ZERO = ZERO  lawful but unevidenced — a claim we decline to make
ZERO × POS = ZERO  evidenced while carrying constraints that were never discharged
NEG × ZERO = NEG   a refusal stands without needing evidence to corroborate it
===============  ==================================================================

ZERO is what makes this a product rather than a conjunction of booleans: two-valued logic
has to lie in one direction or the other about "not checked".

Why this lives in ``libs/python`` and not inside one app
-------------------------------------------------------
The algebra was implemented first in Noetica's ``agent-machine``, where the verdict was a
*caller-supplied field* and all five call sites passed the literal ``'POS'`` — 34 of 53 real
ledger entries recorded ``grounded: false`` alongside ``verdict: 'POS'``. Governance that
lives inside one app is governance one app can quietly drop. Any service on the mesh —
prophet-workspace, agora, ops-fabric-api, prophet-mesh agents — imports this and emits the
same receipt shape, validated by the same contract:

    https://schemas.srcos.ai/v2/LawfulDispatchReceipt.json

Cross-language agreement is enforced by shared vectors, not by trust: both this package and
Noetica's TypeScript implementation are tested against
``sourceos-spec/conformance/lawful-verdict-vectors.json``. Two implementations that each
pass their own unit tests can still disagree with each other; only a shared vector set makes
that detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

__all__ = [
    "Verdict", "Tier", "SeamSource",
    "truth_product", "law_verdict", "evidence_verdict", "evidence_tier",
    "LawFactor", "EvidenceFactor", "Receipt", "DispatchLedger",
    "canonical_json", "content_hash", "SEALED_RE", "MIN_SUPPORT",
]

Verdict = Literal["NEG", "ZERO", "POS"]
Tier = Literal["T1", "T2"]
SeamSource = Literal["measured", "declared"]

_VERDICTS: tuple[Verdict, ...] = ("NEG", "ZERO", "POS")
_RANK: dict[str, int] = {"NEG": 0, "ZERO": 1, "POS": 2}

SEALED_RE = r"^sha256:[0-9a-f]{64}$"
#: House minimum for any statistic. Below this the correct output is "unestablished",
#: not a number with wide error bars presented bare.
MIN_SUPPORT = 30

import re as _re

_SEALED = _re.compile(SEALED_RE)


def truth_product(law: str, evidence: str) -> Verdict:
    """Truth = Law × Evidence. The meet under NEG < ZERO < POS.

    >>> truth_product("POS", "POS")
    'POS'
    >>> truth_product("POS", "ZERO")   # lawful but unevidenced
    'ZERO'
    >>> truth_product("NEG", "NEG")    # NOT 'POS' — sign arithmetic would say +1
    'NEG'

    Raises ValueError on anything that is not a verdict. A bare KeyError from a primitive
    used in tamper-evidence checking tells a caller nothing about what went wrong; the most
    likely cause is a legacy ledger row that carries no factors at all, and the message says
    so. Mirrors the TypeScript ``truthProduct``, which throws for the same reason.
    """
    if law not in _RANK or evidence not in _RANK:
        raise ValueError(
            f"truth_product: not a verdict (law={law!r}, evidence={evidence!r}); "
            f"expected one of {list(_RANK)}. Legacy ledger rows carry no factors — "
            f"guard before multiplying rather than passing None through."
        )
    return _VERDICTS[min(_RANK[law], _RANK[evidence])]


def law_verdict(bar_cleared: bool, residual: Sequence[str]) -> Verdict:
    """The Law factor, DERIVED from the gate decision — never asserted by a caller.

    Undischarged residual yields ZERO, not POS: a bar that "cleared" while carrying
    constraints it could not discharge has *deferred*, not established.
    """
    if not bar_cleared:
        return "NEG"
    return "POS" if len(residual) == 0 else "ZERO"


def evidence_verdict(
    request_hash: str, answer_hash: str, grounded: bool, refuted: bool = False
) -> Verdict:
    """The Evidence factor, DERIVED from what the record actually contains.

    Absent or malformed digests are ZERO — nothing was shown, and nothing was refuted.
    NEG requires an actual refutation, which only an external verifier can supply, so
    ``refuted`` is the one factor input a caller may legitimately set.
    """
    if refuted:
        return "NEG"
    if not _SEALED.match(request_hash or "") or not _SEALED.match(answer_hash or ""):
        return "ZERO"
    return "POS" if grounded else "ZERO"


def evidence_tier(law_source: str, evidence_source: str) -> Tier:
    """T1 (instrumented) only when BOTH factors were measured.

    Claiming T1 for a value no instrument produced is the same defect as asserting a
    verdict, one level up. Under-claiming (T2 when both are measured) is always allowed;
    over-claiming is what the contract forbids.
    """
    return "T1" if law_source == "measured" and evidence_source == "measured" else "T2"


def canonical_json(obj: Any) -> str:
    """Canonical JSON: recursive key sort, no whitespace, non-ASCII emitted RAW.

    ``ensure_ascii=False`` is load-bearing, not stylistic. Python's default escapes ``"café"``
    to ``"caf\u00e9"`` while JavaScript's ``JSON.stringify`` emits it raw, so with the default
    every seal over non-ASCII content diverges between languages — a receipt sealed by
    prophet-workspace would fail to verify inside Noetica the moment it contained an accented
    character. The cross-language seal test did not catch this because the spec's example
    receipt is pure ASCII. Caught in review on prophet-platform#1065; now pinned by the
    ``canonicalJson`` vectors, which include accented text, CJK and astral-plane emoji.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(text: str) -> str:
    """SEAM-C content digest of a string body (request/answer).

    The digest is over ``canonicalJson(text)`` — the QUOTED JSON encoding — not the raw bytes.
    That is not an arbitrary choice: TypeScript's ``contentHash`` is ``ledgerHash(s)``, which
    canonicalises first, and it has already sealed every entry in the production ledger, so it
    defines the function by incumbency. An earlier version here hashed ``text.encode()``
    directly and therefore disagreed with TypeScript on EVERY input
    (``content_hash("hello")`` differed completely). Nothing caught it: the schema only checks
    that a digest is well-formed, and a wrong digest is still well-formed. The ``contentHash``
    vectors now pin the function itself.
    """
    return "sha256:" + hashlib.sha256(canonical_json(text).encode("utf-8")).hexdigest()


def _seal(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LawFactor:
    bar_cleared: bool
    residual: tuple[str, ...] = ()
    source: SeamSource = "measured"

    @property
    def factor(self) -> Verdict:
        return law_verdict(self.bar_cleared, self.residual)

    def to_json(self) -> dict[str, Any]:
        return {"factor": self.factor, "barCleared": self.bar_cleared,
                "residual": list(self.residual), "source": self.source}


@dataclass(frozen=True)
class EvidenceFactor:
    request_hash: str
    answer_hash: str
    grounded: bool
    refuted: bool = False
    source: SeamSource = "measured"

    @property
    def factor(self) -> Verdict:
        return evidence_verdict(self.request_hash, self.answer_hash, self.grounded, self.refuted)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"factor": self.factor, "source": self.source,
                               "grounded": self.grounded}
        # Only emit digests that are well-formed. A malformed digest in the receipt would
        # fail the contract's pattern; omitting it says honestly that nothing was captured.
        if _SEALED.match(self.request_hash or ""):
            out["requestHash"] = self.request_hash
        if _SEALED.match(self.answer_hash or ""):
            out["answerHash"] = self.answer_hash
        if self.refuted:
            out["refuted"] = True
        return out


@dataclass(frozen=True)
class Receipt:
    """A LawfulDispatchReceipt. ``verdict`` and ``evidenceTier`` are DERIVED properties,
    not stored fields — there is deliberately no way to construct one that asserts them."""

    dispatch_id: str
    ts: str
    law: LawFactor
    evidence: EvidenceFactor
    seq: int
    prev: str
    emitter: str | None = None
    schema_version: str = "0.1.0"

    @property
    def verdict(self) -> Verdict:
        return truth_product(self.law.factor, self.evidence.factor)

    @property
    def evidence_tier(self) -> Tier:
        return evidence_tier(self.law.source, self.evidence.source)

    def body(self) -> dict[str, Any]:
        """Everything the seal covers: the whole receipt minus ``seal.attestation``.

        ``evidenceTier`` is INSIDE the seal. It carries governance meaning — T1 asserts the
        verdict was instrumented — so it must not be flippable without breaking the
        attestation. ``seq`` and ``ts`` are inside for the same reason: an entry that could
        be re-ordered or re-dated without breaking its own hash would let a chain be
        rewritten in place.
        """
        out: dict[str, Any] = {
            "schemaVersion": self.schema_version, "kind": "LawfulDispatchReceipt",
            "dispatchId": self.dispatch_id, "ts": self.ts,
            "law": self.law.to_json(), "evidence": self.evidence.to_json(),
            "verdict": self.verdict, "evidenceTier": self.evidence_tier,
            "seal": {"seq": self.seq, "prev": self.prev},
        }
        if self.emitter:
            out["emitter"] = self.emitter
        return out

    def attestation(self) -> str:
        return _seal(self.body())

    def to_json(self) -> dict[str, Any]:
        out = self.body()
        out["seal"] = {**out["seal"], "attestation": self.attestation()}
        return out


GENESIS = "genesis"


@dataclass
class DispatchLedger:
    """An append-only, hash-chained sequence of receipts. Tamper anywhere upstream makes
    every entry from that seam onward unreachable from genesis.

    ``replay`` re-derives the product as well as recomputing the seals. The chain proves a
    record was not altered after the fact; it cannot prove the verdict followed from its
    factors at write time, which is a separate and equally necessary check.
    """

    entries: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self, dispatch_id: str, ts: str, law: LawFactor, evidence: EvidenceFactor,
        emitter: str | None = None,
    ) -> dict[str, Any]:
        prev = self.entries[-1]["seal"]["attestation"] if self.entries else GENESIS
        r = Receipt(dispatch_id=dispatch_id, ts=ts, law=law, evidence=evidence,
                    seq=len(self.entries), prev=prev, emitter=emitter)
        entry = r.to_json()
        self.entries.append(entry)
        return entry

    def replay(self) -> tuple[bool, int, str | None]:
        """Returns ``(ok, validated_count, reason)``. ``validated_count`` is how many
        entries are reachable and consistent from genesis, which is the number that
        matters after a tamper: entries past the seam may remain internally linked to each
        other while being worthless."""
        prev = GENESIS
        for i, e in enumerate(self.entries):
            # replay() validates data that is by assumption UNTRUSTED — catching a forger
            # is the whole job. So every structural surprise must come back as
            # (False, i, reason), never as an exception. A tamper-evidence routine that
            # raises on a malformed entry hands the caller a crash where it promised a
            # verdict, and any caller that wrapped replay() in a bare `except` would read
            # that crash as "not my problem" rather than "this ledger is bad".
            try:
                ok, reason = self._replay_entry(e, prev)
            except Exception as exc:  # noqa: BLE001 — malformed input is a finding, not a bug
                return False, i, f"malformed entry at index {i}: {type(exc).__name__}: {exc}"
            if not ok:
                return False, i, reason
            prev = e["seal"]["attestation"]
        return True, len(self.entries), None

    @staticmethod
    def _replay_entry(e: dict, prev: str) -> tuple[bool, str | None]:
        """One entry's checks. May raise on a malformed entry; replay() converts that into
        a finding. Split out so the fail-closed boundary is one obvious place."""
        seq = e["seal"]["seq"]
        if e["seal"]["prev"] != prev:
            return False, f"prev-link mismatch at seq {seq}"
        body = {k: v for k, v in e.items() if k != "seal"}
        body["seal"] = {"seq": seq, "prev": e["seal"]["prev"]}
        if _seal(body) != e["seal"]["attestation"]:
            return False, f"attestation mismatch (tampered) at seq {seq}"
        derived = truth_product(e["law"]["factor"], e["evidence"]["factor"])
        if e["verdict"] != derived:
            return False, (f"verdict {e['verdict']} does not follow from "
                           f"{e['law']['factor']} × {e['evidence']['factor']} = {derived}")
        # A tier must BE a tier before it can be compared to one. The previous check only
        # rejected T1-claimed-where-T2-is-owed, so any unrecognised value — "T0", "", a
        # number — sailed straight through: forge the tier to something outside the
        # vocabulary and the entry validated. An unreadable governance claim is not a
        # weaker claim than an over-claim; it is a worse one.
        tier = e["evidenceTier"]
        if tier not in ("T1", "T2"):
            return False, f"seq {seq} carries an unknown evidenceTier {tier!r}; expected 'T1' or 'T2'"
        # Under-claiming (T2 where T1 was earned) remains allowed; over-claiming does not.
        if tier == "T1" and evidence_tier(e["law"]["source"], e["evidence"]["source"]) == "T2":
            return False, f"seq {seq} claims T1 on a declared factor"
        return True, None
