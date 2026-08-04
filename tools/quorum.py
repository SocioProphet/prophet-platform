#!/usr/bin/env python3
"""Validator-quorum verification for autonomy admission — the canon's "Genesis Guard".

The Source Canon requires that dangerous / high-autonomy actions are not self-granted: a
QUORUM of independent validators (`min_validators: 3, threshold: 2/3`) must co-sign, and
"every validator keeps its own truth" (each signature is an independent witness). Today the
platform admits with a single membrane decision; this makes the quorum real.

It CONFORMS to the authoritative QuorumProof shape
(mcp-a2a-zero-trust :: schemas/canonical/quorum_proof.schema.json, vendored under
apps/compute-gateway/.../schemas) — we verify that shape, we do not invent one:

    { "rule": "2of3-human",
      "validators": ["spiffe://validators/human1", ...],
      "signed_payload_hash": "sha256:<64hex>",
      "signatures": [ {"kind":"human","spiffe_id":"spiffe://validators/human1","sig":"..."} ] }

`verify_quorum` is fail-closed: any missing field, a rule that doesn't parse, a signer not in
the validator set, a duplicate signer, a payload-hash mismatch, or fewer than `threshold`
signatures → NOT a valid quorum. `quorum_gate` is the Genesis Guard: an autonomy level at or
above a floor requires a valid quorum, else the grant is demoted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

_RULE = re.compile(r"^(\d+)of(\d+)-([a-z]+)$")           # e.g. "2of3-human"
_PAYLOAD_HASH = re.compile(r"^sha256:[a-f0-9]{64}$")
_SIG_MIN_LEN = 16


@dataclass(frozen=True)
class QuorumRule:
    threshold: int
    total: int
    kind: str


def parse_rule(rule: str) -> Optional[QuorumRule]:
    """`MofN-kind` → QuorumRule, or None if malformed / non-sensical (M>N, M<1)."""
    m = _RULE.match(rule or "")
    if not m:
        return None
    threshold, total = int(m.group(1)), int(m.group(2))
    if threshold < 1 or total < 1 or threshold > total:
        return None
    return QuorumRule(threshold, total, m.group(3))


def verify_quorum(proof: dict, *, payload_hash: Optional[str] = None) -> tuple[bool, list[str]]:
    """Fail-closed verification of a QuorumProof against the canonical shape + threshold.

    If `payload_hash` is given, the proof must be over exactly that payload (binds the quorum
    to the thing being admitted). Returns (ok, reasons); reasons is non-empty on failure.
    """
    reasons: list[str] = []
    if not isinstance(proof, dict):
        return False, ["quorum proof is not an object"]

    # required shape
    for field in ("rule", "validators", "signed_payload_hash", "signatures"):
        if field not in proof:
            reasons.append(f"missing required field '{field}'")
    if reasons:
        return False, reasons

    rule = parse_rule(proof["rule"])
    if rule is None:
        return False, [f"rule '{proof['rule']}' does not parse as MofN-kind (M>=1, M<=N)"]

    validators = proof["validators"]
    if not isinstance(validators, list) or not validators:
        return False, ["validators must be a non-empty list"]
    validator_set = set(validators)
    if len(validator_set) != len(validators):
        reasons.append("validators list has duplicates")
    if len(validator_set) < rule.total:
        reasons.append(f"rule needs {rule.total} validators; only {len(validator_set)} listed")

    phash = proof["signed_payload_hash"]
    if not isinstance(phash, str) or not _PAYLOAD_HASH.match(phash):
        reasons.append("signed_payload_hash must be 'sha256:<64hex>'")
    elif payload_hash is not None and phash != payload_hash:
        reasons.append("signed_payload_hash does not match the admitted payload (quorum unbound)")

    sigs = proof["signatures"]
    if not isinstance(sigs, list) or not sigs:
        return False, reasons + ["signatures must be a non-empty list"]

    seen: set[str] = set()
    valid = 0
    for i, s in enumerate(sigs):
        if not isinstance(s, dict) or any(k not in s for k in ("kind", "spiffe_id", "sig")):
            reasons.append(f"signature[{i}] missing kind/spiffe_id/sig")
            continue
        if s["kind"] != rule.kind:
            reasons.append(f"signature[{i}] kind '{s['kind']}' != rule kind '{rule.kind}'")
            continue
        if s["spiffe_id"] not in validator_set:
            reasons.append(f"signature[{i}] signer '{s['spiffe_id']}' is not a listed validator")
            continue
        if s["spiffe_id"] in seen:
            reasons.append(f"signature[{i}] duplicate signer '{s['spiffe_id']}'")
            continue
        if not isinstance(s["sig"], str) or len(s["sig"]) < _SIG_MIN_LEN:
            reasons.append(f"signature[{i}] sig too short / missing")
            continue
        seen.add(s["spiffe_id"])
        valid += 1

    if valid < rule.threshold:
        reasons.append(f"{valid} valid distinct signature(s) < threshold {rule.threshold} "
                       f"(rule {proof['rule']})")

    ok = not reasons
    return ok, reasons


def compose_quorum_proof(rule: str, validators: Iterable[str], payload_hash: str,
                         signatures: Iterable[dict]) -> dict:
    """Assemble a QuorumProof dict (does not sign — callers supply signatures)."""
    return {
        "rule": rule,
        "validators": list(validators),
        "signed_payload_hash": payload_hash,
        "signatures": list(signatures),
    }


def quorum_gate(granted_rank: int, *, floor_rank: int, proof: Optional[dict],
                payload_hash: Optional[str] = None,
                enforce: bool = False) -> dict[str, Any]:
    """Genesis Guard: a grant at or above `floor_rank` requires a valid validator quorum.

    Advisory by default (records the requirement + whether it was met, never lowers the grant),
    so wiring this cannot break the current single-decision admission. With enforce=True an
    unmet quorum DEMOTES the grant to just below the floor — high autonomy is never self-granted.
    """
    if granted_rank < floor_rank:
        return {"quorum_required": False, "quorum_ok": True, "granted_rank": granted_rank,
                "reason": f"L{granted_rank} below quorum floor L{floor_rank}"}
    ok, reasons = (False, ["no quorum proof supplied"]) if proof is None \
        else verify_quorum(proof, payload_hash=payload_hash)
    result = {"quorum_required": True, "quorum_ok": ok, "granted_rank": granted_rank,
              "floor_rank": floor_rank, "reason": "; ".join(reasons) or "quorum satisfied"}
    if not ok and enforce:
        result["granted_rank"] = floor_rank - 1
        result["demoted"] = True
    return result
