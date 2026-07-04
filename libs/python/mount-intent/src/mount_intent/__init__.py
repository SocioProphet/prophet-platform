"""mount_intent — declare storage by intent; get backend + retention/egress policy by construction.

    from mount_intent import MountIntent, Runtime, resolve, may_egress

    resolve(MountIntent.DERIVED_INDEX, Runtime.PODMAN)   # backend + policy
    may_egress(MountIntent.SECRETS)                       # -> False (never leaves the device)
"""
from .intents import (
    EGRESSABLE_INTENTS,
    IntentBinding,
    Layer,
    MountIntent,
    Retention,
    Runtime,
    binding,
    may_cache,
    may_delete,
    may_egress,
    resolve,
)
from .lifecycle import ArtifactState, can_transition, is_terminal, transition
from .schema import MountDeclaration, PolicyDecision

__all__ = [
    "MountIntent", "Layer", "Retention", "Runtime", "IntentBinding",
    "binding", "resolve", "may_egress", "may_cache", "may_delete", "EGRESSABLE_INTENTS",
    "ArtifactState", "can_transition", "transition", "is_terminal",
    "MountDeclaration", "PolicyDecision",
]
