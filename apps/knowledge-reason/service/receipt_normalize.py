from __future__ import annotations

from typing import Any, Dict


def normalize_receipt_payload(receipt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "scopeRef": receipt.get("scopeRef", ""),
        "issuedAt": receipt.get("issuedAt", ""),
        "policyWitnessThreshold": int(receipt.get("policyWitnessThreshold", 0) or 0),
        "witnesses": list(receipt.get("witnesses", [])),
    }
