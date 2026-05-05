from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol


class PolicyError(ValueError):
    """Raised when a policy decision blocks or cannot evaluate an operation."""


class PolicyEngine(Protocol):
    def decide(self, operation: str, resource: dict[str, Any], policy_ref: str | None = None) -> dict[str, Any]: ...


class StaticPolicyEngine:
    """Deterministic policy engine for the first Personal Intelligence Cell lane.

    The first runtime implementation needs explicit policy gates before real
    PolicyFabric integration. This engine is intentionally small: operation names
    map to fixed decisions and every result is a normal policy decision object.
    """

    VALID_DECISIONS = {"allow", "deny", "quarantine", "review_required", "redact"}

    def __init__(self, decisions: dict[str, str] | None = None, default_decision: str = "allow") -> None:
        if default_decision not in self.VALID_DECISIONS:
            raise PolicyError(f"unsupported default policy decision: {default_decision}")
        self._decisions = decisions or {}
        self._default_decision = default_decision
        for operation, decision in self._decisions.items():
            if decision not in self.VALID_DECISIONS:
                raise PolicyError(f"unsupported policy decision {decision!r} for operation {operation!r}")

    def decide(self, operation: str, resource: dict[str, Any], policy_ref: str | None = None) -> dict[str, Any]:
        if not operation:
            raise PolicyError("operation must be non-empty")
        decision = self._decisions.get(operation, self._default_decision)
        resolved_policy_ref = policy_ref or resource.get("policy_ref") or resource.get("relevance_policy") or resource.get("notification_policy") or "policy://cell/default/static"
        return {
            "decision": decision,
            "policy_ref": resolved_policy_ref,
            "reason": f"static policy decision for {operation}",
            "decided_at": _now(),
        }


def require_allowed(decision: dict[str, Any], operation: str) -> dict[str, Any]:
    if decision.get("decision") != "allow":
        raise PolicyError(f"policy blocked {operation}: {decision.get('decision')}")
    return decision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
