from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def check_receipt_policy(carrier: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    receipt = carrier.get("slashTopicReceipt", {})
    issued_at = receipt.get("issuedAt")
    if not issued_at:
        return {"ok": False, "reason": "missingIssuedAt"}
    issued_dt = _parse_ts(issued_at)
    now = datetime.now(timezone.utc)
    max_age = int(policy.get("maxReceiptAgeSeconds", 86400))
    if issued_dt > now + timedelta(minutes=5):
        return {"ok": False, "reason": "issuedInFuture"}
    if now - issued_dt > timedelta(seconds=max_age):
        return {"ok": False, "reason": "receiptExpired"}
    if carrier.get("scopeRef") != receipt.get("scopeRef"):
        return {"ok": False, "reason": "scopeMismatch"}
    required = int(receipt.get("policyWitnessThreshold", policy.get("defaultWitnessThreshold", 2)))
    observed = len(receipt.get("witnesses", []))
    if observed < required:
        return {"ok": False, "reason": "policyWitnessThreshold", "required": required, "observed": observed}
    return {"ok": True, "reason": "ok", "required": required, "observed": observed}
