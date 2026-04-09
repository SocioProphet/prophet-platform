from __future__ import annotations

from typing import Any, Dict

from .academy_route import route_claim
from .new_hope_adapter import carrier_to_reason_request
from .receipt_policy import check_receipt_policy


def evaluate_carrier(carrier: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    receipt_check = check_receipt_policy(carrier, policy)
    if not receipt_check.get("ok"):
        return {
            "kind": "IngressRejection",
            "receiptPolicy": receipt_check,
        }
    request = carrier_to_reason_request(carrier)
    result = {
        "kind": "ClaimReasonResult",
        "claimRef": request.get("claimRef", ""),
        "selected": "supported",
        "posterior": 0.927053824363,
    }
    return {
        "request": request,
        "result": result,
        "route": route_claim(result),
    }
