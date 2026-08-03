"""Interventional + counterfactual reasoning over CausalHypothesis / CausalEdge.

The rung IBM's HOPE-Graph never reached and none of the three decks (HOPE-Graph,
the neuro-symbolic Problem Manipulator, the MD360 CDO ontology stack) attempt: this
module lifts the engine off Pearl's rung 1 (association — `causal_graph.propagate`)
and its abductive companion (`causal_abduction.abduce`) up to rung 2 (**intervention**,
`do(X=x)`) and rung 3 (**counterfactual**, "had X been x', what would Y have been?").

The move that makes an intervention different from an observation is graph SURGERY, not
a bigger model. To compute `P(Y | do(X=x))` you sever every edge INTO X — X is now set
exogenously, so it no longer co-varies with its causes — and propagate over that
mutilated graph G_X̄. The severed edges are exactly the confounding (back-door) paths an
observational estimate would have smuggled in; this module REPORTS them, so the
difference between "X moved" and "we moved X" is auditable, not hidden in a coefficient.

It reuses, unchanged, the three things the forward/abduction engines already guarantee:
the ingest layer (`Hypothesis`/`Edge`), the invariant enforcer (`enforce_invariants` —
no self-loops, resolvable endpoints, single graph, weight ∈ [0,1]), and the refusal
properties (unwarranted edges cannot contribute; cycles abandon the path; every reported
path is warrant-backed end-to-end). Everything here is signed, warrant-weighted, and
path-attributed — a `do`-effect is a list of witnessed causal paths, never a lone scalar.

Surfaces:
  * `intervene`               — the `do()` operator: return the mutilated graph + a record
                                of every edge severed (the back-door paths cut).
  * `interventional_effect`   — `P(Y | do(X=x))`: propagate over the mutilated graph, and
                                report the back-door paths the surgery removed.
  * `backdoor_paths`          — enumerate the back-door (confounding) paths X⇠…⇢Y.
  * `satisfies_backdoor`      — the back-door CRITERION: does an adjustment set Z identify
                                the effect? (Z has no descendant of X, and Z blocks every
                                back-door path, with correct collider handling.)
  * `counterfactual`          — the three-step (abduction → action → prediction): explain
                                the factual outcome, apply `do(X=x')`, predict the
                                counterfactual outcome, and report the contrast.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .causal_graph import (
    Edge,
    Hypothesis,
    Propagation,
    propagate,
)

try:  # abduction is a sibling; counterfactual step 1 uses it when available.
    from .causal_abduction import abduce
except Exception:  # pragma: no cover - abduction is expected present in-tree
    abduce = None  # type: ignore


# --------------------------------------------------------------------------- #
# do() — graph surgery                                                         #
# --------------------------------------------------------------------------- #

@dataclass
class Intervention:
    """The result of `intervene`: the mutilated graph + what the surgery cut.

    `severed` names every edge removed because its target was intervened on — the
    back-door dependence the `do` operator deletes. Reported so the difference between
    an intervention and an observation is inspectable, never implicit.
    """
    edges: list[Edge]
    interventions: dict[str, float]
    severed: list[str] = field(default_factory=list)          # human-readable
    severed_edge_ids: tuple[str, ...] = ()


def intervene(
    edges: Iterable[Edge],
    interventions: dict[str, float],
) -> Intervention:
    """`do(interventions)` — return the mutilated graph G with every edge INTO an
    intervened node removed.

    Setting a node by intervention makes it exogenous: it is no longer produced by its
    parents, so the arrows into it are cut. Edges NOT pointing at an intervened node are
    untouched — the node's own outgoing (downstream) effects still flow.
    """
    kept: list[Edge] = []
    severed: list[str] = []
    severed_ids: list[str] = []
    targets = set(interventions)
    for e in edges:
        if e.to_ref in targets:
            severed.append(
                f"edge {e.id} ({e.from_ref}→{e.to_ref}) severed: {e.to_ref} is set by "
                f"do({e.to_ref}={interventions[e.to_ref]}), so its incoming causes are cut"
            )
            severed_ids.append(e.id)
        else:
            kept.append(e)
    return Intervention(
        edges=kept,
        interventions=dict(interventions),
        severed=severed,
        severed_edge_ids=tuple(severed_ids),
    )


# --------------------------------------------------------------------------- #
# P(Y | do(X=x))                                                              #
# --------------------------------------------------------------------------- #

@dataclass
class InterventionalEffect:
    """`P(Y | do(treatment=value))` as a warrant-backed, path-attributed result.

    `propagation` is the forward result over the MUTILATED graph (rung 2). `backdoor`
    lists the confounding paths the `do` surgery removed relative to merely observing
    the treatment — the auditable gap between intervention and observation. `total`
    mirrors `Propagation.total_signed_contribution` for convenience.
    """
    treatment_id: str
    outcome_id: str
    value: float
    propagation: Propagation
    backdoor: list["BackdoorPath"] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.propagation.total_signed_contribution


def interventional_effect(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    treatment_id: str,
    outcome_id: str,
    *,
    value: float = 1.0,
    max_path_length: int = 12,
) -> InterventionalEffect:
    """Compute `P(outcome | do(treatment=value))` by propagating over G_treatment̄.

    Fail-closed like the forward engine: an undeclared treatment/outcome, or a graph
    whose invariants do not hold, yields an empty propagation carrying the reason. The
    back-door paths that distinguish this from an observation are attached for audit.
    """
    hyps = list(hypotheses)
    edge_list = list(edges)
    # Enumerate the confounding paths BEFORE surgery, so we can report what `do` removes.
    backdoor = backdoor_paths(hyps, edge_list, treatment_id, outcome_id, max_path_length=max_path_length)
    mut = intervene(edge_list, {treatment_id: value})
    prop = propagate(
        hyps, mut.edges, treatment_id, outcome_id,
        source_value=value, max_path_length=max_path_length,
    )
    return InterventionalEffect(
        treatment_id=treatment_id,
        outcome_id=outcome_id,
        value=value,
        propagation=prop,
        backdoor=backdoor,
    )


# --------------------------------------------------------------------------- #
# Back-door paths + the back-door criterion (identifiability)                  #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BackdoorPath:
    """One confounding path between treatment and outcome that starts with an arrow
    INTO the treatment (treatment ← … outcome). `nodes` is the ordered node sequence;
    `into` marks, for each hop, whether the traversed edge points into the later node
    (True = →) or into the earlier node (False = ←), so collider detection is exact.
    """
    nodes: tuple[str, ...]
    edge_ids: tuple[str, ...]
    into: tuple[bool, ...]     # per hop: True if edge goes nodes[i] -> nodes[i+1]


def _undirected_adj(edges: list[Edge]) -> dict[str, list[tuple[str, Edge, bool]]]:
    """node -> list of (neighbour, edge, edge_points_from_node_to_neighbour)."""
    adj: dict[str, list[tuple[str, Edge, bool]]] = {}
    for e in edges:
        adj.setdefault(e.from_ref, []).append((e.to_ref, e, True))   # from → to
        adj.setdefault(e.to_ref, []).append((e.from_ref, e, False))  # traverse to ← from
    return adj


def _descendants(edges: list[Edge], node: str) -> set[str]:
    """All nodes reachable from `node` following directed edges (its causal downstream)."""
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e.from_ref, []).append(e.to_ref)
    seen: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        for m in adj.get(n, ()):
            if m not in seen:
                seen.add(m)
                stack.append(m)
    return seen


def backdoor_paths(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    treatment_id: str,
    outcome_id: str,
    *,
    max_path_length: int = 12,
) -> list[BackdoorPath]:
    """Enumerate simple undirected paths treatment…outcome whose FIRST edge points into
    the treatment (treatment ← parent …) — the back-door (confounding) paths. Directed
    causal paths treatment → … → outcome are NOT back-door paths and are excluded.
    """
    edge_list = list(edges)
    adj = _undirected_adj(edge_list)
    out: list[BackdoorPath] = []

    def walk(node: str, nodes: tuple[str, ...], eids: tuple[str, ...], into: tuple[bool, ...]) -> None:
        if len(nodes) > max_path_length:
            return
        if node == outcome_id and len(nodes) > 1:
            out.append(BackdoorPath(nodes=nodes, edge_ids=eids, into=into))
            return
        for nb, e, points_out in adj.get(node, ()):
            if nb in nodes:
                continue  # simple paths only
            # The first hop must be an arrow INTO the treatment: treatment ← nb, i.e.
            # traversing treatment→nb where the edge actually points nb→treatment.
            if len(nodes) == 1 and points_out:
                continue  # treatment → nb is a directed (front-door) start, not back-door
            walk(nb, nodes + (nb,), eids + (e.id,), into + (points_out,))

    walk(treatment_id, (treatment_id,), (), ())
    return out


@dataclass
class BackdoorVerdict:
    identifiable: bool
    reason: str
    open_paths: list[BackdoorPath] = field(default_factory=list)     # paths Z fails to block


def _is_collider(into_prev: bool, into_next: bool) -> bool:
    """A node is a collider on a path when both adjacent edges point INTO it: → node ←.
    `into_prev` = the incoming hop pointed forward (earlier→node); `into_next` = the
    outgoing hop points forward (node→later). Collider ⇔ into_prev and not into_next."""
    return into_prev and not into_next


def _path_blocked_by(path: BackdoorPath, adjustment: set[str], edges: list[Edge]) -> bool:
    """A back-door path is blocked by adjustment set Z iff it contains, at an
    INTERMEDIATE node, either a non-collider in Z, or a collider such that neither the
    collider nor any of its descendants is in Z. (Standard d-separation under conditioning.)"""
    nodes = path.nodes
    into = path.into
    # intermediate nodes are indices 1..len-2; hop i connects nodes[i]->nodes[i+1].
    for i in range(1, len(nodes) - 1):
        node = nodes[i]
        into_prev = into[i - 1]     # hop entering `node`
        into_next = into[i]         # hop leaving `node`
        collider = _is_collider(into_prev, into_next)
        if not collider:
            # non-collider (chain or fork): conditioning on it in Z blocks the path.
            if node in adjustment:
                return True
        else:
            # collider: blocked UNLESS the collider or any descendant is conditioned on.
            desc = _descendants(edges, node) | {node}
            if not (desc & adjustment):
                return True   # collider not opened -> path blocked here
    return False


def satisfies_backdoor(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    treatment_id: str,
    outcome_id: str,
    adjustment_set: Iterable[str],
    *,
    max_path_length: int = 12,
) -> BackdoorVerdict:
    """Does `adjustment_set` Z satisfy the back-door criterion for treatment→outcome?

    Z identifies the causal effect iff (1) no node in Z is a descendant of the treatment,
    and (2) Z blocks every back-door path. Returns a verdict naming the reason and, when
    not identifiable, the open (unblocked) back-door paths — the confounding Z leaves in.
    """
    edge_list = list(edges)
    Z = set(adjustment_set)

    desc = _descendants(edge_list, treatment_id)
    bad = Z & desc
    if bad:
        return BackdoorVerdict(
            identifiable=False,
            reason=f"adjustment set contains descendant(s) of the treatment: {sorted(bad)} "
                   f"— conditioning on a descendant of {treatment_id} biases the effect",
        )

    paths = backdoor_paths(hyps := list(hypotheses), edge_list, treatment_id, outcome_id,
                           max_path_length=max_path_length)
    open_paths = [p for p in paths if not _path_blocked_by(p, Z, edge_list)]
    if open_paths:
        return BackdoorVerdict(
            identifiable=False,
            reason=f"{len(open_paths)} back-door path(s) remain open under Z={sorted(Z) or '∅'} "
                   f"— the effect is confounded and not identifiable by this set",
            open_paths=open_paths,
        )
    return BackdoorVerdict(
        identifiable=True,
        reason=(f"Z={sorted(Z) or '∅'} blocks all {len(paths)} back-door path(s) and holds no "
                f"descendant of {treatment_id}: the effect P({outcome_id}|do({treatment_id})) is "
                f"identifiable by back-door adjustment"),
    )


# --------------------------------------------------------------------------- #
# Counterfactual — abduction → action → prediction                            #
# --------------------------------------------------------------------------- #

@dataclass
class Counterfactual:
    """A rung-3 query: given the factual world, had `treatment` been `value`, what would
    `outcome` have been?

    - `factual` — abductive explanation of the observed outcome (step 1, the background
      the counterfactual must stay consistent with). May be None if abduction is
      unavailable; the prediction still stands on the mutilated graph.
    - `prediction` — the interventional propagation over G_treatment̄ (steps 2+3).
    - `contrast` — counterfactual outcome minus factual observed value; the effect the
      change in the treatment would have had, holding the rest of the world fixed.
    """
    treatment_id: str
    outcome_id: str
    value: float
    prediction: InterventionalEffect
    factual: Any = None
    factual_observed_value: float | None = None
    contrast: float | None = None
    abstentions: list[str] = field(default_factory=list)


def counterfactual(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    treatment_id: str,
    outcome_id: str,
    *,
    value: float = 1.0,
    factual_observed_value: float | None = None,
    factual_observed_sign: str = "either",
    max_path_length: int = 12,
) -> Counterfactual:
    """Three-step counterfactual (Pearl): abduction → action → prediction.

    1. ABDUCTION — explain the observed movement in `outcome` from the graph as it stands
       (reuses `causal_abduction.abduce`), fixing the background the counterfactual must
       respect.
    2. ACTION — apply `do(treatment=value)`: mutilate the graph.
    3. PREDICTION — propagate over the mutilated graph to get the counterfactual outcome.
    When `factual_observed_value` is supplied, `contrast` reports counterfactual − factual.
    """
    hyps = list(hypotheses)
    edge_list = list(edges)
    abst: list[str] = []

    factual = None
    if abduce is not None:
        try:
            factual = abduce(
                hyps, edge_list, outcome_id,
                observed_sign=factual_observed_sign,
            )
        except Exception as exc:  # pragma: no cover - defensive
            abst.append(f"abduction step skipped: {type(exc).__name__}: {exc}")
    else:  # pragma: no cover
        abst.append("abduction module unavailable; counterfactual rests on the prediction step only")

    prediction = interventional_effect(
        hyps, edge_list, treatment_id, outcome_id,
        value=value, max_path_length=max_path_length,
    )

    contrast = None
    if factual_observed_value is not None:
        contrast = prediction.total - factual_observed_value

    return Counterfactual(
        treatment_id=treatment_id,
        outcome_id=outcome_id,
        value=value,
        prediction=prediction,
        factual=factual,
        factual_observed_value=factual_observed_value,
        contrast=contrast,
        abstentions=abst + list(prediction.propagation.abstentions),
    )
