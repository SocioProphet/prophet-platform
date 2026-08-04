"""Declaration schema for a mount intent + the auditable policy decision.

A workload declares a MountDeclaration (name → intent → path). The platform resolves it to a
backend + policy, and every egress/caching/deletion decision produces an auditable
PolicyDecision (Layer 5: the Policy Engine records events to the append-only Audit Log).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .intents import (
    LinkAvailability,
    MountIntent,
    Runtime,
    binding,
    check_single_egress,
    resolve,
    verified_immutable,
)

_VERITY_ROOT_HASH = re.compile(r"^[0-9a-f]{64}$")  # dm-verity root hash (sha256), hex


class MountDeclaration(BaseModel):
    """What a workload declares for one mounted path."""

    name: str = Field(..., description="volume/mount name")
    intent: MountIntent
    mount_path: str = Field(..., description="container path")
    link_availability: LinkAvailability = Field(
        default=LinkAvailability.RELIABLE,
        description="edge↔twin link reliability — decides reference vs copy for egress mounts",
    )
    verity_root_hash: Optional[str] = Field(
        default=None,
        description="dm-verity root hash (64-hex), pinned in the manifest — REQUIRED for "
                    "verified-immutable intents (curated_corpus). Makes corpus integrity a "
                    "signature check, not a trust assertion.",
    )

    @model_validator(mode="after")
    def _verity_pinned_when_required(self) -> "MountDeclaration":
        if verified_immutable(self.intent):
            if not self.verity_root_hash:
                raise ValueError(
                    f"{self.intent.value} is verified-immutable and MUST pin a verity_root_hash "
                    f"in the manifest (squashfs/erofs + dm-verity)"
                )
            if not _VERITY_ROOT_HASH.match(self.verity_root_hash):
                raise ValueError("verity_root_hash must be a 64-char hex sha256 digest")
        elif self.verity_root_hash:
            raise ValueError(
                f"{self.intent.value} is not verified-immutable — a verity_root_hash is meaningless"
            )
        return self

    def resolved(self, runtime: Runtime) -> dict:
        return {
            "name": self.name,
            "mount_path": self.mount_path,
            "verity_root_hash": self.verity_root_hash,
            **resolve(self.intent, runtime, self.link_availability),
        }


class WorkloadDeclaration(BaseModel):
    """A workload's full set of mounts. Enforces the single-egress-chokepoint invariant by
    construction: at most one egress mount, and it must be named — the only mount whose
    contents survive the pod, so egress attestation has exactly one home."""

    name: str = Field(..., description="workload name")
    mounts: list[MountDeclaration] = Field(default_factory=list)

    @model_validator(mode="after")
    def _single_egress(self) -> "WorkloadDeclaration":
        violations = check_single_egress([m.intent for m in self.mounts])
        if violations:
            raise ValueError(f"{self.name}: " + "; ".join(violations))
        return self

    def resolved(self, runtime: Runtime) -> list[dict]:
        return [m.resolved(runtime) for m in self.mounts]


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
