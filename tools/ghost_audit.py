"""Ghost audit — the first measurement of "ghostry".

From the gapi→TriTRPC recon: ghostry is the degree to which an actor can cause
state changes WITHOUT crossing an observable/attestable edge. The capability
membrane's receipts make that quantifiable: a state change is attested iff a
membrane receipt ENFORCED an ALLOW for it.

    ghost surface = any state delta with no preceding enforced-allow receipt
                    (missing, un-enforced/observed, denied, or — under
                    require_signed — unsigned/forged).

This replays a receipt journal against the observed state deltas and reports the
ghosts + a ghostry score in [0,1] (0 = fully attested, 1 = every change a ghost).
Governance you cannot falsify is theater; ghostry you cannot measure is a hope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

# Only an ENFORCED ALLOW authorizes a state change. Everything else — a deferred
# ask, a denial, or an OBSERVED (foreign, unenforceable) verdict — leaves any
# resulting state delta a ghost.
AUTHORIZING_VERDICT = "allowed"


@dataclass
class StateDelta:
    """An observed change to durable state that claims some authorizing receipt."""
    id: str
    action: str
    subject: str
    authorized_by: Optional[str] = None   # receipt id it claims authorized it
    at: str = ""
    is_erasure: bool = False              # a deletion/redaction — needs a Proof-of-Emptiness


@dataclass
class Ghost:
    delta_id: str
    reason: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"deltaId": self.delta_id, "reason": self.reason, "detail": self.detail}


@dataclass
class GhostReport:
    total_deltas: int
    attested: int
    ghosts: List[Ghost] = field(default_factory=list)

    @property
    def ghostry(self) -> float:
        return 0.0 if self.total_deltas == 0 else round(len(self.ghosts) / self.total_deltas, 6)

    @property
    def clean(self) -> bool:
        return not self.ghosts

    def to_dict(self) -> Dict[str, Any]:
        by_reason: Dict[str, int] = {}
        for g in self.ghosts:
            by_reason[g.reason] = by_reason.get(g.reason, 0) + 1
        return {
            "type": "GhostAuditReport",
            "specVersion": "0.1.0",
            "totalDeltas": self.total_deltas,
            "attested": self.attested,
            "ghostCount": len(self.ghosts),
            "ghostry": self.ghostry,
            "byReason": by_reason,
            "ghosts": [g.to_dict() for g in self.ghosts],
        }


def _receipt_of(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Journal entries may be sealed records (with .receipt) or bare receipts."""
    return entry.get("receipt", entry) if isinstance(entry, dict) else {}


def audit(
    journal: Sequence[Dict[str, Any]],
    deltas: Sequence[StateDelta],
    *,
    require_signed: bool = False,
    verify: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> GhostReport:
    """Replay the journal against the deltas and surface the ghost set.

    require_signed: entries must be sealed records with a valid signature to
    count as authorizing (defends against a forged/absent receipt). `verify` is
    a callable (e.g. membrane_identity.verify_sealed) taking the sealed record.
    """
    from tools.proof_of_emptiness import is_valid_poe

    # Index authorizing receipts: enforced ALLOW, optionally signature-verified.
    # Proof-of-Emptiness receipts are indexed separately — an erasure is authorized
    # by a *valid PoE*, never by an ordinary enforced-allow (that would be a silent sink).
    authorizing: Dict[str, str] = {}   # receipt_id -> failure reason ("" = ok)
    poe_ok: Dict[str, bool] = {}       # receipt_id -> is this a valid Proof-of-Emptiness
    signed_ok: Dict[str, bool] = {}
    for entry in journal:
        rc = _receipt_of(entry)
        rid = rc.get("id")
        if not rid:
            continue
        if rc.get("type") == "ProofOfEmptiness":
            poe_ok[rid] = is_valid_poe(entry)
            continue
        if require_signed:
            sig_ok = bool(verify and verify(entry) if isinstance(entry, dict) and "signature" in entry else False)
            signed_ok[rid] = sig_ok
        if not rc.get("enforced", False):
            authorizing[rid] = "not_enforced"       # observed / advisory
        elif rc.get("verdict") != AUTHORIZING_VERDICT:
            authorizing[rid] = "not_allowed"         # denied / deferred
        else:
            authorizing[rid] = ""                    # enforced allow

    ghosts: List[Ghost] = []
    attested = 0
    for d in deltas:
        rid = d.authorized_by

        # Erasures obey the stricter no-silent-sinks rule: a certified PoE, or ghost.
        if d.is_erasure:
            if not rid:
                ghosts.append(Ghost(d.id, "uncertified_erase", "deletion with no Proof-of-Emptiness"))
            elif rid in poe_ok:
                if poe_ok[rid]:
                    attested += 1
                else:
                    ghosts.append(Ghost(d.id, "uncertified_erase", f"PoE {rid} did not reach ∅ (H(X₀)≠H(∅))"))
            elif rid in authorizing:
                ghosts.append(Ghost(d.id, "not_a_proof_of_emptiness",
                                    f"deletion authorized by ordinary receipt {rid} (silent sink)"))
            else:
                ghosts.append(Ghost(d.id, "receipt_missing", f"claims PoE {rid} absent from journal"))
            continue

        if not rid:
            ghosts.append(Ghost(d.id, "no_receipt", "state change with no authorizing receipt"))
            continue
        if rid not in authorizing:
            ghosts.append(Ghost(d.id, "receipt_missing", f"claims receipt {rid} absent from journal"))
            continue
        reason = authorizing[rid]
        if reason:
            ghosts.append(Ghost(d.id, reason, f"authorizing receipt {rid} was {reason}"))
            continue
        if require_signed and not signed_ok.get(rid, False):
            ghosts.append(Ghost(d.id, "bad_signature", f"receipt {rid} unsigned or signature invalid"))
            continue
        attested += 1
    return GhostReport(total_deltas=len(deltas), attested=attested, ghosts=ghosts)


def _load_deltas(raw: Sequence[Dict[str, Any]]) -> List[StateDelta]:
    return [
        StateDelta(id=d["id"], action=d.get("action", ""), subject=d.get("subject", ""),
                   authorized_by=d.get("authorized_by"), at=d.get("at", ""),
                   is_erasure=bool(d.get("is_erasure", False)))
        for d in raw
    ]


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Measure ghostry: state deltas with no enforced-allow receipt.")
    p.add_argument("--journal", required=True, help="JSON array of sealed receipts / receipts")
    p.add_argument("--deltas", required=True, help="JSON array of {id, action, subject, authorized_by}")
    p.add_argument("--require-signed", action="store_true")
    p.add_argument("--out", type=str)
    args = p.parse_args(argv)

    journal = json.loads(open(args.journal, encoding="utf-8").read())
    deltas = _load_deltas(json.loads(open(args.deltas, encoding="utf-8").read()))
    verify = None
    if args.require_signed:
        try:
            from tools.membrane_identity import verify_sealed as verify  # type: ignore
        except Exception:
            verify = None
    report = audit(journal, deltas, require_signed=args.require_signed, verify=verify)
    out = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out + "\n")
    else:
        print(out)
    # Non-zero when any ghost is found, so CI/guards can gate on ghostry == 0.
    return 0 if report.clean else 4


__all__ = ["StateDelta", "Ghost", "GhostReport", "audit"]


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(_cli(_sys.argv[1:]))
