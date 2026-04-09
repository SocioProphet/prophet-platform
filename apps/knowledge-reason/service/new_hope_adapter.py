from __future__ import annotations

from typing import Any, Dict, List


def carrier_to_reason_request(carrier: Dict[str, Any]) -> Dict[str, Any]:
    claim = carrier.get("claim", {})
    citations: List[Dict[str, Any]] = carrier.get("citations", [])
    return {
        "kind": "ClaimReasonRequest",
        "scopeRef": carrier.get("scopeRef", ""),
        "claimRef": claim.get("claimRef", ""),
        "statement": {
            "subject": claim.get("subject", ""),
            "predicate": claim.get("predicate", ""),
            "object": claim.get("object", ""),
        },
        "citations": [
            {
                "citationRef": c.get("citationRef", ""),
                "artifactRef": c.get("artifactRef", ""),
            }
            for c in citations
        ],
    }
