"""Governed receipts — the moat, applied to notebook execution.

Every cell run produces a sealed, hash-chained receipt (in-toto-flavoured):
what code, over what runtime, producing what outputs, when, by whom. Receipts
chain per project so the whole session is tamper-evident and replayable. Best-
effort mirrored to the governance ledger; the local chain is the source of truth.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any

import httpx

LEDGER_URL = os.environ.get("GOVERNANCE_LEDGER_URL", "").rstrip("/")

# per-project chain: project -> list[receipt]
_CHAINS: dict[str, list[dict]] = {}


def _sha(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def seal(project: str, *, adapter: str, language: str, runtime: str,
         code: str, outputs: list[dict], status: str, actor: str) -> dict:
    chain = _CHAINS.setdefault(project, [])
    prev = chain[-1]["id"] if chain else None
    body = {
        "adapter": adapter, "language": language, "runtime": runtime,
        "code_sha": _sha(code), "outputs_sha": _sha(outputs),
        "status": status, "actor": actor, "prev": prev,
        "ts": time.time(),
    }
    receipt = {"id": _sha(body), "project": project, **body}
    chain.append(receipt)
    _mirror(receipt)
    return receipt


def chain(project: str) -> list[dict]:
    return list(_CHAINS.get(project, []))


def verify(project: str) -> dict:
    """Re-prove the chain: recompute every id from its body and re-walk every prev.

    The moat made checkable. For each stored receipt we rebuild the exact body
    `seal` hashed (everything the receipt carries EXCEPT its own `id` and
    `project`), recompute `_sha(body)`, and confirm it equals the stored `id` —
    catching any tampered field (code, outputs, status, actor, timestamp). We
    also confirm each `prev` points at the previous receipt's `id` (the first is
    None), catching reordered or excised links. Returns at the FIRST break so
    `broken_at` names the earliest compromised receipt — something a mutable
    audit log (Databricks) structurally cannot offer.
    """
    ch = _CHAINS.get(project, [])
    prev_id: str | None = None
    for r in ch:
        body = {k: v for k, v in r.items() if k not in ("id", "project")}
        if _sha(body) != r["id"]:
            return {"valid": False, "count": len(ch), "broken_at": r["id"],
                    "reason": "id does not match recomputed body hash (tampered receipt)"}
        if r["prev"] != prev_id:
            return {"valid": False, "count": len(ch), "broken_at": r["id"],
                    "reason": "prev does not link to the previous receipt (broken chain)"}
        prev_id = r["id"]
    return {"valid": True, "count": len(ch), "broken_at": None, "reason": None}


def _mirror(receipt: dict) -> None:
    """Best-effort mirror to the governance ledger; never blocks execution."""
    if not LEDGER_URL:
        return
    try:
        httpx.post(f"{LEDGER_URL}/v1/receipts", json=receipt, timeout=2.0)
    except Exception:  # pragma: no cover - ledger is best-effort
        pass


def new_id() -> str:
    return uuid.uuid4().hex[:12]
