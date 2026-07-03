"""Declaration schema for a mount intent + the auditable policy decision.

A workload declares a MountDeclaration (name → intent → path). The platform resolves it to a
backend + policy, and every egress/caching/deletion decision produces an auditable
PolicyDecision (Layer 5: the Policy Engine records events to the append-only Audit Log).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .intents import MountIntent, Runtime, binding, resolve


class MountDeclaration(BaseModel):
    """What a workload declares for one mounted path."""

    name: str = Field(..., description="volume/mount name")
    intent: MountIntent
    mount_path: str = Field(..., description="container path")

    def resolved(self, runtime: Runtime) -> dict:
        return {"name": self.name, "mount_path": self.mount_path, **resolve(self.intent, runtime)}


Gate = Literal["egress", "caching", "deletion"]


class PolicyDecision(BaseModel):
    """An auditable decision by the Policy Engine for one gate on one intent."""

    gate: Gate
    intent: MountIntent
    allowed: bool
    reason: str
    decided_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def egress(cls, intent: MountIntent) -> "PolicyDecision":
        b = binding(intent)
        return cls(
            gate="egress", intent=intent, allowed=b.may_egress,
            reason=(
                f"{intent.value} is layer={b.layer.value}; "
                + ("egress permitted (still subject to residency/ACL)" if b.may_egress
                   else "must not leave the device (rebuildable/ephemeral/sensitive)")
            ),
        )

    @classmethod
    def caching(cls, intent: MountIntent) -> "PolicyDecision":
        b = binding(intent)
        return cls(
            gate="caching", intent=intent, allowed=b.may_cache,
            reason=("vendor-materializable (re-materialized from canonical)" if b.may_cache
                    else "not eligible for vendor caching"),
        )

    @classmethod
    def deletion(cls, intent: MountIntent) -> "PolicyDecision":
        from .intents import may_delete
        allowed = may_delete(intent)
        return cls(
            gate="deletion", intent=intent, allowed=allowed,
            reason=("freely collectable (rebuildable/ttl/ephemeral)" if allowed
                    else "durable — deletion is retention-gated (scheduler + legal hold)"),
        )
