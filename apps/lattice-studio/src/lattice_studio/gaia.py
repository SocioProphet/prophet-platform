"""GAIA Ontogenesis Stewardship Graph — vocabulary + the epistemic invariant.

Ported from Noetica/agent-machine/lib/gaia-ontology.ts (vendored from regis-entity-graph). GAIA is the estate's
canonical living-knowledge ontology (IOES: Identity, Ontogenesis, Ecology, Stewardship). It already defines a
governed writeback pattern — a steward's decision (keeper / successor / developmental phase / acknowledged
abandonment signals) persisted on the node as gaia_* properties and honored on read.

The one that matters for the moat: GAIA invariant #2 — "Model inference alone must not promote developmental
state to canonical human-impacting truth." We enforce it *through our epistemic status*: a phase set by a
human steward is `attested`; a phase set by a model/agent is `derived` (it can observe staleness, not canonize
it). GAIA governance and the proof-carrying moat become the same mechanism.
"""
from __future__ import annotations

from typing import Any

GAIA_NODE_KINDS = [
    "LIVING_ENTITY", "ONTOGENESIS_STATE", "GAIA_DEPENDENCY_RECORD", "STEWARDSHIP_RECORD", "KEEPER_LOG",
    "SUCCESSION_RULE", "ABANDONMENT_SIGNAL", "LEARNING_ARTIFACT", "DELIVERY_OUTCOME_RECORD", "POLICY_DECISION",
    "CONSENT_RECEIPT", "PROJECTION_RECORD",
]
GAIA_EDGE_KINDS = [
    "STEWARD_OF", "GUARDIAN_OF", "MENTOR_OF", "APPRENTICE_OF", "SUCCESSOR_OF", "PRESERVES", "TRANSMITS_TO",
    "CARES_FOR", "HAS_KEEPER_LOG", "HAS_SUCCESSION_RULE", "HAS_ABANDONMENT_SIGNAL", "HAS_ONTOGENESIS_STATE",
    "DEPENDS_ON", "CONTRIBUTES_TO", "IMPACTS", "CO_EVOLVES_WITH", "REGENERATES", "DEGRADES",
    "AUTHORIZED_BY_CONSENT", "ALLOWED_BY_POLICY", "DENIED_BY_POLICY", "ATTESTED_BY_PROOF", "EMITTED_BY_EXECUTION",
    "HAS_DELIVERY_OUTCOME", "HAS_LEARNING_CHANGESET",
]
ONTOGENESIS_PHASES = ["seed", "formation", "growth", "maturity", "transmission", "transformation",
                      "decline", "succession", "archive", "termination"]
ABANDONMENT_SIGNALS = ["no_active_keeper", "no_successor", "review_overdue", "broken_contact", "stale_evidence",
                       "contested_authority", "critical_dependency_failed", "orphaned_artifact"]
GAIA_INVARIANTS = [
    "Stewardship must not imply ownership without a separate ownership/authority artifact.",
    "Model inference alone must not promote developmental state to canonical human-impacting truth.",
    "Material dependencies must not be stripped merely to simplify projection.",
    "A stewardship record without an active keeper becomes needs_review or orphaned, not silently healthy.",
    "Abandonment is a graph state, not absence of graph data.",
]

# actor_kind → the epistemic status a developmental-phase assertion carries (invariant #2).
_HUMAN_KINDS = {"human", "steward", "keeper"}


def phase_epistemic(actor_kind: str) -> str:
    """A phase set by a human steward is `attested` (canonical); by a model/agent it is `derived` — observed,
    not promoted to canonical human-impacting truth. This IS GAIA invariant #2, enforced through epistemic status."""
    return "attested" if (actor_kind or "human").lower() in _HUMAN_KINDS else "derived"


def stewardship_of(props: dict[str, Any] | None) -> dict[str, Any]:
    """Read the persisted stewardship decision off a node's gaia_* properties (what the census honors)."""
    p = props or {}
    resolved = [s.strip() for s in str(p.get("gaia_resolved_signals", "")).split(",") if s.strip()]
    keeper = p.get("gaia_keeper") or None
    return {
        "keeper": keeper,
        "successor": p.get("gaia_successor") or None,
        "phase_override": p.get("gaia_phase_override") or None,
        "phase_epistemic": p.get("gaia_phase_epistemic") or None,
        "resolved_signals": resolved,
        "reviewed_at": p.get("gaia_reviewed_at") or None,
        "note": p.get("gaia_steward_note") or None,
        "stewarded": bool(keeper or resolved or p.get("gaia_phase_override") or p.get("gaia_reviewed_at")),
    }
