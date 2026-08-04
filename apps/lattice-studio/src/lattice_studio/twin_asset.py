"""AssetTwin — the FOURTH twin, extending the three-twin closure (knowledge/HellGraph, human/HDT,
Earth/GAIA) to physical, owned property: a house, car, appliance, or network device a real person
claims on the map and configures.

A twin:Claim carries a twin:AssetState — a promotion lattice CLAIMED -> SEALED -> CONFIGURED ->
AGENTIC_ACTIVE (+ the terminal REVOKED, reachable from any live state) -- the SAME governed-evidence
discipline as the other three twins: the AssetState IS the epistemic ladder. The invariant mirrors
HDT's exactly: a model/agent may claim/seal/configure an asset, but only the owning human identity
(or a policy actor) may promote it to AGENTIC_ACTIVE -- standing autonomous authority over a piece of
owned property is a human decision, never a model's own escalation.

Sealing (CLAIMED -> SEALED) is cryptographic, not epistemic: it happens via identity-twin's /attest
(Ed25519 + VRF context-binding on the vendored Multiverseal Twin), independent of who acts. A claim
that fails to seal (identity-twin unreachable) still lands at CLAIMED -- honest degradation, the same
pattern hellgraph-service's GATEWAY_RECEIPTS uses: the record is never blocked on the seal succeeding.
"""
from __future__ import annotations

ASSET_STATES = ["CLAIMED", "SEALED", "CONFIGURED", "AGENTIC_ACTIVE", "REVOKED"]
ASSET_TYPES = {"house", "car", "appliance", "network_device", "room", "device"}
# The human-facing lens (a smart-home reference taxonomy): group by FUNCTION, not by protocol/device
# type -- the view an operator/owner actually wants when reviewing what they've claimed.
FUNCTION_TAXONOMY = {"safety", "multimedia", "climate_comfort", "control_savings"}
_HUMAN_KINDS = {"human", "owner", "steward", "keeper", "policy"}


def is_human(actor_kind: str) -> bool:
    return (actor_kind or "human").lower() in _HUMAN_KINDS


def epistemic_for_state(state: str, sealed: bool) -> str:
    """CLAIMED = observed (an owner's assertion, not yet cryptographically bound); SEALED/CONFIGURED =
    attested once identity-twin's /attest has bound the claim (else they stay observed, honestly
    degraded); AGENTIC_ACTIVE = verified (a human granted standing autonomous authority -- a stronger
    claim than a bare assertion); REVOKED = observed (the fact of revocation is asserted immediately,
    not gated on a fresh cryptographic seal)."""
    if state == "REVOKED":
        return "observed"
    if state == "AGENTIC_ACTIVE":
        return "verified"
    return "attested" if sealed else "observed"


def can_promote(actor_kind: str, target_state: str) -> bool:
    """The invariant: a model/agent may claim, seal, or configure an asset, but only the owning human
    identity (or a policy actor) may promote it to AGENTIC_ACTIVE. Mirrors HDT's can_promote_omega:
    the SAME shape, a different terminal gate."""
    return not (target_state == "AGENTIC_ACTIVE" and not is_human(actor_kind))


def claim_of(props: dict | None) -> dict:
    p = props or {}
    return {
        "asset_type": p.get("asset_type"),
        "owner_identity": p.get("owner_identity"),
        "function_tag": p.get("function_tag") or None,
        "state": p.get("state", "CLAIMED"),
        "sealed": bool(p.get("sealed")),
        "epistemic_mode": p.get("epistemic_mode"),
    }
