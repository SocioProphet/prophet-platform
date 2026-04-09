from __future__ import annotations

from typing import Any, Dict


def route_claim(result: Dict[str, Any]) -> Dict[str, Any]:
    selected = result.get("selected", "unknown")
    if selected == "supported":
        return {
            "academyContext": "AtlasCodex",
            "lane": "canon-candidate",
            "action": "materialize-candidate",
        }
    return {
        "academyContext": "OracleOfDelphi",
        "lane": "review-queue",
        "action": "queue-review",
    }
