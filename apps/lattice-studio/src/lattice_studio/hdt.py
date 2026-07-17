"""HDT — the Human Digital Twin, the third twin (from ontogenesis.ttl `hdt:`).

An hdt:Observation (a FHIR resource about a person) carries an hdt:OmegaState — a promotion lattice
ABSENT → SEEDED → NORMALIZED → LINKED → TRUSTED → ACTIONABLE → DELIVERED — plus a KFS membership triad
(Cognition/Values/Action). This is the SAME governed-evidence discipline as the knowledge and Earth twins:
the OmegaState membrane IS the epistemic ladder, and — the invariant — a model may seed/normalize but only a
human/clinician/policy actor may deliver an observation to canonical, human-actionable truth.
"""
from __future__ import annotations

from typing import Any

HDT_NS = "https://socioprophet.dev/ont/ontogenesis#"     # hdt: lives in the ontogenesis root
OMEGA_STATES = ["ABSENT", "SEEDED", "NORMALIZED", "LINKED", "TRUSTED", "ACTIONABLE", "DELIVERED"]
TRIAD_ROLES = {"CBD": "Cognition", "CGT": "Values", "NHY": "Action"}   # the KFS membership triad
_HUMAN_KINDS = {"human", "clinician", "steward", "keeper", "policy"}


def is_human(actor_kind: str) -> bool:
    return (actor_kind or "human").lower() in _HUMAN_KINDS


def epistemic_for_omega(state: str, actor_kind: str) -> str:
    """The OmegaState lattice mapped to epistemic status — the SAME mechanism as the other two twins.
    DELIVERED = canonical human-actionable truth → attested (only a human/policy reaches it); TRUSTED/ACTIONABLE
    → verified; NORMALIZED/LINKED → observed (human) / derived (model); ABSENT/SEEDED → observed / hypothesis."""
    if state == "DELIVERED":
        return "attested"
    if state in ("TRUSTED", "ACTIONABLE"):
        return "verified"
    if state in ("NORMALIZED", "LINKED"):
        return "observed" if is_human(actor_kind) else "derived"
    return "observed" if is_human(actor_kind) else "hypothesis"     # ABSENT / SEEDED


def can_promote_omega(actor_kind: str, target_state: str) -> bool:
    """The invariant: a model/agent may advance an observation through the lattice, but only a human/clinician/
    policy actor may DELIVER it to canonical, human-actionable truth."""
    return not (target_state == "DELIVERED" and not is_human(actor_kind))


def observation_of(props: dict[str, Any] | None) -> dict[str, Any]:
    p = props or {}
    return {"code": p.get("code") or None, "value": p.get("value") if p.get("value") != "" else None,
            "omega_state": p.get("omega_state", "ABSENT"), "epistemic_mode": p.get("epistemic_mode"),
            "membership": {"CBD": p.get("m_cbd"), "CGT": p.get("m_cgt"), "NHY": p.get("m_nhy")}}
