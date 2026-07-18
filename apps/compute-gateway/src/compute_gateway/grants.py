"""The grant lifecycle — request → policy decision → quorum → issue → ledger →
validate → revoke. The deep integration with OUR authority kernel
(SocioProphet/mcp-a2a-zero-trust), beyond the self-issued ToolGrantCheck seam.

A ToolGrantCheck (zerotrust.py) records whether a grant is valid at dispatch. THIS
module is where grants come FROM: a PolicyDecision classifies the operation's
danger, HIGH-danger operations (user code) require a human QUORUM before a Grant is
issued, every state change appends a ledger event, and revocation is authoritative
— a revoked grant fails every subsequent check closed.

Conforms exactly to the vendored kernel schemas (grant / policy_decision /
quorum_proof). This is the reference decision the kernel would make; the transport
seam (`ISSUER`, `set_transport`) forwards to the real kernel over noetica-mcp /
TriTRPC when wired — the contract and the ledger shape never change.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from typing import Any

from . import registry, signing

ISSUER = os.getenv("ZEROTRUST_ISSUER", "spiffe://socioprophet.dev/compute-gateway")
DEFAULT_TTL = int(os.getenv("GRANT_TTL_SEC", "3600"))

# effect (registry) → danger class + whether a human quorum is required to issue
_DANGER = {"read": "LOW", "compute": "MEDIUM", "write": "MEDIUM", "egress": "HIGH", "exec": "HIGH"}
_EFFECT = {"notebook": "exec", "spark": "exec", "graph-query": "read",
           "graph-stats": "read", "inference": "compute", "workflow": "compute"}

_GRANTS: dict[str, dict[str, Any]] = {}
_REVOKED: set[str] = set()
_LEDGER: list[dict[str, Any]] = []


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _policy_hash() -> str:
    return _sha256("entitlements:" + os.getenv("COMPUTE_ENTITLEMENTS", ""))


def _ledger_add(op: str, grant_id: str, **extra: Any) -> None:
    _LEDGER.append({"op": op, "grant_id": grant_id, "at": _now(), **extra})


def decide(kind: str, backend: str) -> dict[str, Any]:
    """A conforming PolicyDecision: danger class + required quorum + constraints.
    HIGH-danger (user-code) operations require a 1-of-N human quorum to issue."""
    effect = _EFFECT.get(kind, "compute")
    danger = _DANGER.get(effect, "MEDIUM")
    required_quorum = 1 if danger == "HIGH" else 0
    return {
        "allow": True,
        "danger_class": danger,
        "policy_hash": _policy_hash(),
        "reason": f"{kind}:{backend} classified {danger} (effect={effect})",
        "constraints": {"ttl_sec": DEFAULT_TTL},
        "required_quorum": required_quorum,
    }


def _quorum_proof(operation: str, signatures: list[dict]) -> dict[str, Any]:
    return {
        "rule": "1-of-N-human",
        "validators": [s["spiffe_id"] for s in signatures],
        "signed_payload_hash": _sha256("quorum:" + operation),
        "signatures": [{"kind": "human", "spiffe_id": s["spiffe_id"], "sig": s["sig"]}
                       for s in signatures],
    }


def request_grant(*, kind: str, backend: str, project: str, actor: str,
                  session: str | None, quorum_signatures: list[dict] | None) -> dict[str, Any]:
    """Run the full flow. Returns {decision, grant|None, quorum_required}. A grant
    issues only if the decision allows AND any required quorum is satisfied."""
    decision = decide(kind, backend)
    sigs = quorum_signatures or []
    need = decision["required_quorum"]
    if need and len(sigs) < need:
        _ledger_add("OP_GRANT_DENY", "-", reason="insufficient quorum", operation=f"{kind}:{backend}")
        return {"decision": decision, "grant": None, "quorum_required": need,
                "reason": f"HIGH-danger operation requires {need} human quorum signature(s)"}

    effect = _EFFECT.get(kind, "compute")
    gid = "grant-" + uuid.uuid4().hex
    op = f"{kind}:{backend}"
    qp = _quorum_proof(op, sigs) if need else None
    aum = _sha256(f"aum:{project}:{actor}:{session or '-'}")
    grant: dict[str, Any] = {
        "grant_id": gid,
        "issued_at": _now(),
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                    time.gmtime(time.time() + DEFAULT_TTL)),
        "binding": {"spiffe_id": f"{ISSUER}/{project}/{actor}", "aum_digest": aum,
                    **({"session_id": session} if session and len(session) >= 6 else {})},
        "capability": {
            "kind": "mcp_tool",
            "capability_ref": f"cap:compute:{kind}",
            "capability_digest": _sha256(f"compute:{kind}:{backend}"),
            "server": "compute-gateway", "tool": f"compute.{kind}",
            "operation": op, "effect": effect,
        },
        "constraints": decision["constraints"],
        "policy_hash": decision["policy_hash"],
    }
    if qp:
        grant["quorum_proof"] = qp
    key = signing.load_signing_key()
    if key is not None:
        sig, _pub = signing.sign_statement(grant, key)
        if sig:
            grant["sig"] = {"issuer": ISSUER, "sig": sig}

    _GRANTS[gid] = grant
    _ledger_add("OP_GRANT_ISSUE", gid, operation=op, danger=decision["danger_class"])
    return {"decision": decision, "grant": grant, "quorum_required": 0}


def validate(grant_id: str, operation: str | None = None) -> dict[str, Any]:
    """Authoritative validity check → {valid, expired, revoked, reason}. Revoked or
    expired grants fail closed. Appends an OP_GRANT_VALIDATE ledger event."""
    g = _GRANTS.get(grant_id)
    if g is None:
        _ledger_add("OP_GRANT_VALIDATE", grant_id, valid=False, reason="unknown")
        return {"valid": False, "expired": False, "revoked": False, "reason": "unknown grant"}
    revoked = grant_id in _REVOKED
    expired = g["expires_at"] < _now()
    op_ok = operation is None or g["capability"]["operation"] == operation
    valid = not revoked and not expired and op_ok
    reason = ("revoked" if revoked else "expired" if expired
              else "operation mismatch" if not op_ok else "valid")
    _ledger_add("OP_GRANT_VALIDATE", grant_id, valid=valid, reason=reason)
    return {"valid": valid, "expired": expired, "revoked": revoked, "reason": reason}


def revoke(grant_id: str) -> bool:
    """Revoke a grant. Authoritative — every subsequent validate fails closed."""
    if grant_id not in _GRANTS:
        return False
    _REVOKED.add(grant_id)
    _ledger_add("OP_GRANT_REVOKE", grant_id)
    return True


def get(grant_id: str) -> dict[str, Any] | None:
    return _GRANTS.get(grant_id)


def ledger() -> list[dict[str, Any]]:
    return list(_LEDGER)


def _reset() -> None:   # test hook
    _GRANTS.clear()
    _REVOKED.clear()
    _LEDGER.clear()
