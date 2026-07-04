"""Artifact lifecycle state machine (diagram 2).

Grounds retention: every artifact moves through a fixed set of states, and the Retention
Scheduler / Policy Engine only advances it along permitted transitions. Legal hold and
abuse/safety flags interpose *before* deletion; vendor materialization is a disposable side
branch that always re-materializes from canonical.

    IngestedRaw → Normalized → Extracted → Indexed → Served
    Served ⇄ VendorMaterialized → ExpiredVendorCache → (re-materialize) → Served
    Served → FlaggedRetention → (window ends) → Deleted
    Served → LegalHold → (released) → Served | Deleted
    Normalized|Extracted|Indexed → (retention policy) → Deleted
"""
from __future__ import annotations

from enum import Enum


class ArtifactState(str, Enum):
    INGESTED_RAW = "IngestedRaw"
    NORMALIZED = "Normalized"
    EXTRACTED = "Extracted"
    INDEXED = "Indexed"
    SERVED = "Served"
    VENDOR_MATERIALIZED = "VendorMaterialized"
    EXPIRED_VENDOR_CACHE = "ExpiredVendorCache"
    FLAGGED_RETENTION = "FlaggedRetention"
    LEGAL_HOLD = "LegalHold"
    DELETED = "Deleted"


_S = ArtifactState

# Permitted transitions (edges in diagram 2). Any transition not listed is rejected.
_TRANSITIONS: dict[ArtifactState, frozenset[ArtifactState]] = {
    _S.INGESTED_RAW: frozenset({_S.NORMALIZED}),
    _S.NORMALIZED: frozenset({_S.EXTRACTED, _S.DELETED}),
    _S.EXTRACTED: frozenset({_S.INDEXED, _S.DELETED}),
    _S.INDEXED: frozenset({_S.SERVED, _S.DELETED}),
    _S.SERVED: frozenset({_S.VENDOR_MATERIALIZED, _S.FLAGGED_RETENTION, _S.LEGAL_HOLD}),
    _S.VENDOR_MATERIALIZED: frozenset({_S.EXPIRED_VENDOR_CACHE}),
    _S.EXPIRED_VENDOR_CACHE: frozenset({_S.SERVED}),  # re-materialize from canonical
    _S.FLAGGED_RETENTION: frozenset({_S.DELETED, _S.SERVED}),  # window ends → delete; or cleared
    _S.LEGAL_HOLD: frozenset({_S.SERVED, _S.DELETED}),  # released → serve; or policy-permitted delete
    _S.DELETED: frozenset(),  # terminal
}

# A hold blocks deletion until released — deletion attempts from these states are refused.
DELETION_BLOCKED_STATES: frozenset[ArtifactState] = frozenset({_S.LEGAL_HOLD})


def can_transition(src: ArtifactState, dst: ArtifactState) -> bool:
    return dst in _TRANSITIONS.get(src, frozenset())


def transition(src: ArtifactState, dst: ArtifactState) -> ArtifactState:
    """Advance state, refusing illegal moves and deletion under a hold."""
    if dst == ArtifactState.DELETED and src in DELETION_BLOCKED_STATES:
        raise ValueError(f"deletion blocked: {src.value} must be released before deletion")
    if not can_transition(src, dst):
        raise ValueError(f"illegal artifact transition: {src.value} → {dst.value}")
    return dst


def is_terminal(state: ArtifactState) -> bool:
    return len(_TRANSITIONS.get(state, frozenset())) == 0
