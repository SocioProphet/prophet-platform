"""The holography disclosure gate — enforced in the swarm plane (INV-22..26).

When a swarm agent asks for a projection ``π_S(T)`` of a subject ``T`` at scope ``S``,
this gate decides, per field, whether the field is disclosed. Two things make it a
*holography* gate rather than an ordinary allow-list:

**INV-26 — Holographic Completeness (the genuinely new invariant).** The domain of the
projection is ALWAYS the full field set ``F``. A denied field is not dropped to ``⊥``
(absent); it is present as a structured :class:`Denial` carrying the reason and the
policy row that denied it. A photograph cropped to a region shows nothing outside the
frame; a hologram shard still reconstructs the whole scene, blurrier. So a denial here
still reveals the *shape* of what was withheld and *why* — you can always tell a field
was refused apart from a field that does not exist.

**Trust dilates soft budgets, never hard prohibitions.** Legality (L1) is a polytope
``K = {v : A_hard·v ≤ b_hard  ∧  A_soft·v ≤ t·b_soft}``. The hard facets are absolute
prohibitions (e.g. ``¬(HEALTH ∧ ADS)``) and do NOT move with trust ``t`` — a governance
control a dropdown could raise trust past is not a control. Only the soft budget facets
dilate. Readiness (L2) is the Ω lattice. Admission of a field is ``L1 ∧ L2``.

Pure and dependency-free so it drops into any Python service on the mesh, and so the
invariants below are unit-tested rather than asserted.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import Mapping, Sequence, Union

# ── Ω readiness lattice (L2) ────────────────────────────────────────────────
# ABSENT is the bottom; a field must have reached at least its required state to disclose.
OMEGA: tuple[str, ...] = (
    "ABSENT", "SEEDED", "NORMALIZED", "LINKED", "TRUSTED", "ACTIONABLE", "DELIVERED",
)


def _omega_rank(state: str) -> int:
    try:
        return OMEGA.index(state)
    except ValueError:
        return 0  # an unknown state is treated as the bottom (fail-closed)


@dataclass(frozen=True)
class Permit:
    """A disclosed field and the handle to its value."""
    value_ref: str


@dataclass(frozen=True)
class Denial:
    """A withheld field — present in the projection, never absent (INV-26)."""
    reason: str
    policy_ref: str
    # Failure CLASS, so a caller can tell an architecturally-illegal field (never
    # earnable, at any trust) from one that is merely not-yet-ready (earnable):
    #   "polytope" → L1 legality  ·  "omega" → L2 readiness
    cls: str

    @property
    def earnable(self) -> bool:
        """omega denials can be earned by advancing readiness; polytope denials cannot."""
        return self.cls == "omega"


Decision = Mapping[str, Union[Permit, Denial]]


@dataclass(frozen=True)
class Policy:
    """The disclosure polytope + readiness requirements for a subject class."""
    # Fields that are ABSOLUTELY prohibited — hard facets. Never dilate with trust.
    hard_prohibitions: frozenset[str] = _field(default_factory=frozenset)
    # Per-field soft cost in [0, 1]; disclosed only when cost ≤ trust·soft_budget.
    soft_costs: Mapping[str, float] = _field(default_factory=dict)
    soft_budget: float = 1.0
    # Minimum Ω state a field must have reached to be disclosed.
    required_readiness: Mapping[str, str] = _field(default_factory=dict)


def _l1(field: str, trust: float, policy: Policy) -> Denial | None:
    """L1 legality — hard prohibitions are absolute; soft budgets dilate with trust."""
    if field in policy.hard_prohibitions:
        return Denial(
            reason=f"{field} is an absolute prohibition (hard facet — never dilates)",
            policy_ref=f"polytope:hard:{field}", cls="polytope",
        )
    cost = policy.soft_costs.get(field, 0.0)
    if cost > trust * policy.soft_budget + 1e-9:
        return Denial(
            reason=f"{field} exceeds the soft budget at trust {trust:g} "
                   f"(cost {cost:g} > {trust * policy.soft_budget:g})",
            policy_ref=f"polytope:soft:{field}", cls="polytope",
        )
    return None


def _l2(field: str, readiness: Mapping[str, str], policy: Policy) -> Denial | None:
    """L2 readiness — the field must have reached its required Ω state."""
    required = policy.required_readiness.get(field)
    if required is None:
        return None
    have = readiness.get(field, "ABSENT")
    if _omega_rank(have) < _omega_rank(required):
        return Denial(
            reason=f"{field} not ready ({have} < required {required})",
            policy_ref=f"omega:{field}:{required}", cls="omega",
        )
    return None


def holographic_project(
    fields: Sequence[str],
    *,
    trust: float,
    readiness: Mapping[str, str] | None = None,
    policy: Policy,
) -> Decision:
    """Project ``fields`` under ``policy`` at ``trust`` and ``readiness``.

    Returns a decision whose domain is EXACTLY ``fields`` (INV-26): each field maps to a
    :class:`Permit` or a :class:`Denial` — never to nothing. L1 (legality) is checked
    before L2 (readiness), so an architecturally-illegal field is reported as such even
    when it happens to be ready.
    """
    readiness = readiness or {}
    out: dict[str, Union[Permit, Denial]] = {}
    for f in fields:
        denial = _l1(f, trust, policy) or _l2(f, readiness, policy)
        out[f] = denial if denial is not None else Permit(value_ref=f"ref:{f}")
    return out


def disclosed(decision: Decision) -> frozenset[str]:
    """The fields actually disclosed (permitted)."""
    return frozenset(k for k, v in decision.items() if isinstance(v, Permit))


def denials(decision: Decision) -> dict[str, Denial]:
    """The withheld fields and their structured reasons."""
    return {k: v for k, v in decision.items() if isinstance(v, Denial)}
