"""Workspace Operation Plane integration boundary stubs.

These are deliberately small interfaces for the first runtime slice. They keep
policy evaluation, ledger persistence, and agent authority outside the runtime
while giving downstream repos stable seams to implement against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class BoundaryResult:
    """Generic allow/deny style result for boundary checks."""

    allowed: bool
    reason: str = ""
    responsible_actor: str = "system"
    remediation_options: tuple[str, ...] = ()
    audit_required: bool = True
    evidence_refs: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)


class PolicyClient(Protocol):
    """Policy Fabric boundary.

    Real implementations belong in `SocioProphet/policy-fabric` and should
    return `PolicyGateRecord` shaped evidence. The runtime should not embed
    policy rules.
    """

    def evaluate_command(self, command: Mapping[str, Any], operation: Mapping[str, Any] | None = None) -> BoundaryResult:
        """Evaluate whether a command is allowed."""


class LedgerSink(Protocol):
    """Ledger/evidence boundary.

    Real implementations belong in `SocioProphet/prophet-core-ledger` or a
    platform adapter that writes to it. The runtime emits event dictionaries;
    the sink records evidence.
    """

    def record_event(self, event: Mapping[str, Any]) -> None:
        """Record a runtime event as evidence."""


class AgentAuthorityHook(Protocol):
    """Agent authority boundary.

    Real implementations should check `SocioProphet/agent-registry` and
    `SocioProphet/agentplane` records. The runtime should not grant ambient
    authority to agents.
    """

    def authorize_actor(self, actor: Mapping[str, Any], action: str, resource: Mapping[str, Any]) -> BoundaryResult:
        """Authorize an actor for an action on a resource."""


class AllowAllPolicyClient:
    """Development-only policy client that allows commands.

    This is useful for smoke tests. Do not use as production policy authority.
    """

    def evaluate_command(self, command: Mapping[str, Any], operation: Mapping[str, Any] | None = None) -> BoundaryResult:
        return BoundaryResult(allowed=True, reason="development policy boundary allows command")


class NoopLedgerSink:
    """Development-only ledger sink that records nothing."""

    def record_event(self, event: Mapping[str, Any]) -> None:
        return None


class AllowAllAgentAuthorityHook:
    """Development-only agent authority hook.

    This hook allows all actors for smoke tests. Production code must use Agent
    Registry and AgentPlane backed authorization.
    """

    def authorize_actor(self, actor: Mapping[str, Any], action: str, resource: Mapping[str, Any]) -> BoundaryResult:
        return BoundaryResult(allowed=True, reason="development agent boundary allows actor")
