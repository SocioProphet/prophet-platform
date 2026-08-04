"""The holography gate's invariants, pinned. Each maps to an INV-2x from the design."""
from __future__ import annotations

from holography_gate import (
    Policy, Permit, Denial, holographic_project, disclosed, denials, OMEGA,
)

FIELDS = ["name", "email", "health_status", "ad_targeting", "location"]

POLICY = Policy(
    # ¬(HEALTH ∧ ADS): both are hard-prohibited from this projection class, at any trust.
    hard_prohibitions=frozenset({"health_status", "ad_targeting"}),
    soft_costs={"email": 0.4, "location": 0.9},   # location is expensive; email cheap
    soft_budget=1.0,
    required_readiness={"email": "TRUSTED", "location": "LINKED"},
)


def test_inv26_completeness_domain_is_always_the_full_field_set():
    """INV-26: even when everything is denied, every field is PRESENT (never ⊥)."""
    for trust in (0.0, 0.5, 1.0):
        d = holographic_project(FIELDS, trust=trust, policy=POLICY)
        assert set(d.keys()) == set(FIELDS)
        # nothing is absent — each field is a Permit or a Denial, never missing/None
        assert all(isinstance(v, (Permit, Denial)) for v in d.values())


def test_a_denied_field_carries_reason_and_policy_ref_not_absence():
    d = holographic_project(["health_status"], trust=1.0, policy=POLICY)
    v = d["health_status"]
    assert isinstance(v, Denial)
    assert v.reason and v.policy_ref  # the SHAPE of the withheld field is visible


def test_hard_prohibition_never_dilates_even_at_max_trust():
    """A hard facet stays denied at trust 1.0 with full readiness — not earnable."""
    d = holographic_project(
        ["health_status", "ad_targeting"], trust=1.0,
        readiness={"health_status": "DELIVERED", "ad_targeting": "DELIVERED"},
        policy=POLICY,
    )
    for f in ("health_status", "ad_targeting"):
        assert isinstance(d[f], Denial)
        assert d[f].cls == "polytope"
        assert d[f].earnable is False   # architecturally illegal, unearnable


def test_soft_budget_dilates_with_trust():
    """`location` (cost 0.9) is denied at low trust, permitted once trust buys the budget."""
    ready = {"location": "DELIVERED"}   # L2 satisfied so we isolate L1
    low = holographic_project(["location"], trust=0.5, readiness=ready, policy=POLICY)
    high = holographic_project(["location"], trust=1.0, readiness=ready, policy=POLICY)
    assert isinstance(low["location"], Denial) and low["location"].cls == "polytope"
    assert isinstance(high["location"], Permit)


def test_permits_are_monotone_non_decreasing_in_trust():
    """I(T; π_S(T)) monotone: raising trust never REVOKES a disclosed field."""
    ready = {f: "DELIVERED" for f in FIELDS}
    prev: frozenset[str] = frozenset()
    for trust in (0.0, 0.25, 0.5, 0.75, 1.0):
        got = disclosed(holographic_project(FIELDS, trust=trust, readiness=ready, policy=POLICY))
        assert prev <= got, f"trust {trust} revoked a previously-disclosed field: {prev - got}"
        prev = got


def test_readiness_denial_is_earnable_and_classed_omega():
    """A not-yet-ready field is denied with cls 'omega' and IS earnable by advancing Ω."""
    not_ready = holographic_project(["email"], trust=1.0, readiness={"email": "SEEDED"}, policy=POLICY)
    assert isinstance(not_ready["email"], Denial)
    assert not_ready["email"].cls == "omega" and not_ready["email"].earnable is True
    now_ready = holographic_project(["email"], trust=1.0, readiness={"email": "TRUSTED"}, policy=POLICY)
    assert isinstance(now_ready["email"], Permit)


def test_l1_is_checked_before_l2():
    """A hard-prohibited field reports polytope (legality), not omega, even when unready."""
    d = holographic_project(["health_status"], trust=1.0, readiness={"health_status": "ABSENT"}, policy=POLICY)
    assert d["health_status"].cls == "polytope"


def test_disclosed_and_denials_partition_the_fields():
    d = holographic_project(FIELDS, trust=0.5, readiness={"email": "TRUSTED"}, policy=POLICY)
    assert disclosed(d) | set(denials(d)) == set(FIELDS)
    assert disclosed(d).isdisjoint(set(denials(d)))


def test_omega_lattice_is_a_total_order_bottom_absent():
    assert OMEGA[0] == "ABSENT" and OMEGA[-1] == "DELIVERED"
    assert len(set(OMEGA)) == len(OMEGA)   # no duplicate states
