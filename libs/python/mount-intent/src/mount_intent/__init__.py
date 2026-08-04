"""mount_intent — declare storage by intent; get backend + retention/egress policy by construction.

    from mount_intent import MountIntent, Runtime, resolve, may_egress

    resolve(MountIntent.DERIVED_INDEX, Runtime.PODMAN)   # backend + policy
    may_egress(MountIntent.SECRETS)                       # -> False (never leaves the device)
"""
from .intents import (
    EGRESS_DIRECTION_INTENTS,
    EGRESSABLE_INTENTS,
    Direction,
    IntentBinding,
    Layer,
    LinkAvailability,
    MountIntent,
    Retention,
    Runtime,
    binding,
    check_single_egress,
    direction,
    may_cache,
    may_delete,
    may_egress,
    resolve,
    tenant_scoped_source,
    verified_immutable,
)
from .lifecycle import ArtifactState, can_transition, is_terminal, transition
from .schema import MountDeclaration, PolicyDecision, WorkloadDeclaration

__all__ = [
    "MountIntent", "Layer", "Retention", "Runtime", "IntentBinding",
    "Direction", "LinkAvailability",
    "binding", "resolve", "may_egress", "may_cache", "may_delete", "EGRESSABLE_INTENTS",
    "direction", "verified_immutable", "tenant_scoped_source",
    "check_single_egress", "EGRESS_DIRECTION_INTENTS",
    "ArtifactState", "can_transition", "transition", "is_terminal",
    "MountDeclaration", "WorkloadDeclaration", "PolicyDecision",
]
