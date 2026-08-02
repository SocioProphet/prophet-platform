#!/usr/bin/env python3
"""Causal identification engine — Ecosystem Simulation Substrate, Wave 1.

The governance layer (Layer A) of the two-layer architecture: it decides *may we
claim this*, never *what is the value*. Before any solver runs, a scenario's
estimand is checked for identifiability against the structural causal graph.

Three outcomes (spec §2):
  * identified                 — a valid backdoor adjustment set exists (measured).
  * identified_under_assumption — only under a named, epistemically-penalised
                                  assumption (e.g. an unmeasured confounder absent).
  * not_identified             — REFUSE the point estimate; return the blocking
                                  structure and the measurement that would identify it.

This is "no invisible authority" applied to inference: no number reaches a
customer without a declared identification path. `gate` enforces that a solver is
never invoked on an estimand Layer A has not cleared.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Optional


@dataclass
class Dag:
    """A structural causal DAG. `measured` marks observable variables."""

    nodes: set[str]
    edges: list[tuple[str, str]]  # (parent -> child)
    measured: set[str]

    def parents(self, n: str) -> set[str]:
        return {u for (u, v) in self.edges if v == n}

    def children(self, n: str) -> set[str]:
        return {v for (u, v) in self.edges if u == n}

    def descendants(self, start: str) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for c in self.children(cur):
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen

    def ancestors(self, of: set[str]) -> set[str]:
        seen: set[str] = set(of)
        stack = list(of)
        while stack:
            cur = stack.pop()
            for p in self.parents(cur):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    def without_outgoing(self, node: str) -> "Dag":
        """The backdoor graph: drop edges leaving `node`."""
        return Dag(set(self.nodes), [(u, v) for (u, v) in self.edges if u != node], set(self.measured))


def d_separated(dag: Dag, x: str, y: str, z: set[str]) -> bool:
    """Test X ⊥ Y | Z via the ancestral-moralization criterion (correct d-sep)."""
    keep = dag.ancestors({x, y} | set(z))
    # Undirected moral graph over the ancestral subgraph.
    adj: dict[str, set[str]] = {n: set() for n in keep}
    for (u, v) in dag.edges:
        if u in keep and v in keep:
            adj[u].add(v)
            adj[v].add(u)
    # Marry co-parents (parents sharing a child) within the subgraph.
    for n in keep:
        ps = [p for p in dag.parents(n) if p in keep]
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                adj[ps[i]].add(ps[j])
                adj[ps[j]].add(ps[i])
    # Remove the conditioning set, then test reachability x -> y.
    blocked = set(z)
    if x in blocked or y in blocked:
        return True
    stack = [x]
    seen = {x}
    while stack:
        cur = stack.pop()
        if cur == y:
            return False  # an active path exists
        for nb in adj.get(cur, ()):
            if nb not in seen and nb not in blocked:
                seen.add(nb)
                stack.append(nb)
    return True


# Identification statuses.
IDENTIFIED = "identified"
IDENTIFIED_UNDER_ASSUMPTION = "identified_under_assumption"
NOT_IDENTIFIED = "not_identified"


@dataclass
class IdentificationReport:
    estimand_id: str
    status: str
    adjustment_set: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    measurement_to_identify: list[str] = field(default_factory=list)
    blocking_structure: list[str] = field(default_factory=list)

    @property
    def clearable(self) -> bool:
        """True if a solver may run (identified, possibly under assumption)."""
        return self.status in (IDENTIFIED, IDENTIFIED_UNDER_ASSUMPTION)


# Cap the subset search so a pathological graph can't blow up 2**n. Real
# structural graphs at this layer are small; beyond the cap we fall back to the
# full candidate set rather than search, which is conservative (never a false
# positive — an unblockable set just reports not-identified).
_MAX_SEARCH = 12


def _find_adjustment(dag: Dag, t: str, y: str, pool: set[str]) -> Optional[list[str]]:
    """Smallest valid backdoor adjustment set drawn from `pool`, or None.

    Searches subsets smallest-first, so the FIRST hit is minimal by construction
    and a collider in `pool` is simply left out when a smaller set d-separates —
    fixing the false-negative of conditioning on the whole pool at once.
    """
    ordered = sorted(pool)
    if len(ordered) > _MAX_SEARCH:
        return list(ordered) if d_separated(dag, t, y, pool) else None
    for r in range(len(ordered) + 1):
        for subset in combinations(ordered, r):
            if d_separated(dag, t, y, set(subset)):
                return list(subset)
    return None


def identify(
    dag: Dag,
    treatment: str,
    outcome: str,
    estimand_id: str = "estimand",
    *,
    assume_unconfounded: Optional[set[str]] = None,
) -> IdentificationReport:
    """Attempt backdoor identification of treatment→outcome on `dag`."""
    assume_unconfounded = assume_unconfounded or set()
    backdoor = dag.without_outgoing(treatment)
    non_desc = dag.nodes - dag.descendants(treatment) - {treatment, outcome}
    measured_nd = non_desc & dag.measured

    # 1. A valid, minimal adjustment set drawn only from MEASURED non-descendants.
    z = _find_adjustment(backdoor, treatment, outcome, measured_nd)
    if z is not None:
        return IdentificationReport(estimand_id, IDENTIFIED, adjustment_set=sorted(z))

    # 2. A valid set exists but needs currently-unmeasured variables.
    z_all = _find_adjustment(backdoor, treatment, outcome, non_desc)
    if z_all is not None:
        needed = sorted(set(z_all) - dag.measured)
        remaining = [u for u in needed if u not in assume_unconfounded]
        if not remaining:
            return IdentificationReport(estimand_id, IDENTIFIED_UNDER_ASSUMPTION,
                                        adjustment_set=sorted(z_all),
                                        assumptions=[f"no_confounding_via:{u}" for u in needed])
        return IdentificationReport(estimand_id, NOT_IDENTIFIED,
                                    measurement_to_identify=remaining,
                                    blocking_structure=[f"unblocked_backdoor_via:{u}" for u in remaining])

    # 3. No adjustment set d-separates even with everything measured: structurally
    # unidentifiable by adjustment (needs an instrument / different design).
    return IdentificationReport(estimand_id, NOT_IDENTIFIED,
                                blocking_structure=["no_valid_adjustment_set:needs_instrument_or_design"])


class UnidentifiedEstimand(Exception):
    """Raised when a solver is asked to run on an uncleared estimand (fail-closed)."""


def gate(report: IdentificationReport, solver: Callable[[], object]) -> object:
    """Layer-A gate: run `solver` only if the estimand is clearable.

    Enforces that Layer B never computes a number Layer A has not cleared. On a
    non-identified estimand this raises rather than returning a point estimate.
    """
    if not report.clearable:
        raise UnidentifiedEstimand(
            f"{report.estimand_id}: {report.status}; "
            f"measure {report.measurement_to_identify or 'n/a'} to identify"
        )
    return solver()
