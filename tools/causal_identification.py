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
from typing import Callable, Iterable, Optional


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


def _minimal(dag: Dag, t: str, y: str, candidate: set[str]) -> list[str]:
    """Greedily drop nodes that are not needed to keep d-separation."""
    z = set(candidate)
    for node in sorted(candidate):
        if d_separated(dag, t, y, z - {node}):
            z.discard(node)
    return sorted(z)


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
    desc = dag.descendants(treatment)
    non_desc = dag.nodes - desc - {treatment, outcome}
    z_measured = non_desc & dag.measured
    z_all = non_desc

    if d_separated(backdoor, treatment, outcome, z_measured):
        return IdentificationReport(estimand_id, IDENTIFIED,
                                    adjustment_set=_minimal(backdoor, treatment, outcome, z_measured))

    if d_separated(backdoor, treatment, outcome, z_all):
        # A set exists, but it requires currently-unmeasured variables.
        needed = sorted(
            u for u in (z_all - dag.measured)
            if not d_separated(backdoor, treatment, outcome, z_all - {u})
        )
        remaining = [u for u in needed if u not in assume_unconfounded]
        if not remaining:
            return IdentificationReport(estimand_id, IDENTIFIED_UNDER_ASSUMPTION,
                                        adjustment_set=_minimal(backdoor, treatment, outcome, z_all),
                                        assumptions=[f"no_confounding_via:{u}" for u in needed])
        return IdentificationReport(estimand_id, NOT_IDENTIFIED,
                                    measurement_to_identify=remaining,
                                    blocking_structure=[f"unblocked_backdoor_via:{u}" for u in remaining])

    # No adjustment set d-separates even with everything measured: structurally
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
