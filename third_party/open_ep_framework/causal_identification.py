"""ECO-1 — causal identification, estimand registry, and the refusal path.

The exposed route for backward causal reasoning (the 13-artifact map flagged
`causal_abduction.py` as having "no exposed route", blocking the economics
flywheel). This module is the **SCM governance layer**: it decides *whether a
causal claim may be made at all* before any solver computes a value.

Two layers, never conflated (SP-ARCH-002 D5 / BMG-1):

- **SCM layer (governance, here):** given a causal graph and an estimand
  ``P(outcome | do(treatment))``, attempt identification. Answers *may we claim*.
- **Solver layer (execution):** computes the number, reusing
  ``causal_graph.propagate``. Answers *what is the value*.

``run_scenario`` gates the second on the first: **the solver never runs on an
unidentified estimand.** That is no-invisible-authority applied to inference —
no number reaches a caller without a declared identification path.

Three outcomes (Ecosystem Simulation Substrate v2 §2):

- **IDENTIFIED** — a valid backdoor adjustment set of *observed* variables exists;
  it is declared.
- **IDENTIFIED_UNDER_ASSUMPTION** — identification needs a named assumption
  (e.g. no unobserved confounding); the solver runs but the result is
  epistemically penalised and the assumption travels with it.
- **NOT_IDENTIFIED** — no observational quantity yields the causal answer. The
  point estimate is **refused**; the caller gets the blocking structure and the
  measurement that would identify it.

Modal class (``ModalClass``) is Pearl's ladder — observational / interventional /
counterfactual — an axis **orthogonal** to epistemicLevel (SP-ARCH-000 D-I): it
says *what kind of question* is being asked, not *how trustworthy* the answer is.

Scope (increment 1): standard backdoor identification over a DAG. Front-door and
full do-calculus ID are follow-ups; the refusal path is exact regardless.

Stdlib-only.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from open_ep_framework.causal_graph import Edge, Hypothesis, propagate


class ModalClass(str, Enum):
    """Pearl's ladder. Orthogonal to epistemicLevel (SP-ARCH-000 D-I)."""

    OBSERVATIONAL = "observational"
    INTERVENTIONAL = "interventional"
    COUNTERFACTUAL = "counterfactual"


class IdentificationOutcome(str, Enum):
    IDENTIFIED = "identified"
    IDENTIFIED_UNDER_ASSUMPTION = "identified_under_assumption"
    NOT_IDENTIFIED = "not_identified"


NO_UNOBSERVED_CONFOUNDING = "no-unobserved-confounding"


@dataclass(frozen=True)
class Estimand:
    """A causal query ``P(outcome | do(treatment))`` over a named graph."""

    graph_ref: str
    treatment: str
    outcome: str
    query: str = "ate"
    modal_class: ModalClass = ModalClass.INTERVENTIONAL

    @property
    def id(self) -> str:
        raw = f"{self.graph_ref}|{self.treatment}|{self.outcome}|{self.query}|{self.modal_class.value}"
        return "est." + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class EstimandRegistry:
    """A content-addressed registry of estimands. Deterministic ids; idempotent
    registration (same estimand → same id, never a silent overwrite of a
    different one)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Estimand] = {}

    def register(self, estimand: Estimand) -> str:
        eid = estimand.id
        existing = self._by_id.get(eid)
        if existing is not None and existing != estimand:
            raise ValueError(f"estimand id collision for {eid!r}")
        self._by_id[eid] = estimand
        return eid

    def get(self, eid: str) -> Estimand:
        return self._by_id[eid]

    def __len__(self) -> int:
        return len(self._by_id)


@dataclass(frozen=True)
class IdentificationResult:
    outcome: IdentificationOutcome
    estimand_id: str
    adjustment_set: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    blocking_paths: tuple[tuple[str, ...], ...] = ()
    required_measurements: tuple[str, ...] = ()
    epistemic_penalty: int = 0
    rationale: str = ""

    @property
    def identified(self) -> bool:
        return self.outcome != IdentificationOutcome.NOT_IDENTIFIED


@dataclass
class ScenarioResult:
    estimand_id: str
    modal_class: ModalClass
    identification: IdentificationResult
    refused: bool
    point_estimate: float | None = None
    required_measurements: tuple[str, ...] = ()
    blocking_paths: tuple[tuple[str, ...], ...] = ()
    rationale: str = ""
    witnessed_paths: list[object] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Graph helpers (directed DAG over Edge.from_ref -> Edge.to_ref).
# --------------------------------------------------------------------------- #

def _directed(edges: Iterable[Edge]) -> set[tuple[str, str]]:
    return {(e.from_ref, e.to_ref) for e in edges if e.from_ref != e.to_ref}


def _neighbours(directed: set[tuple[str, str]]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for a, b in directed:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def _descendants(directed: set[tuple[str, str]], node: str) -> set[str]:
    children: dict[str, set[str]] = {}
    for a, b in directed:
        children.setdefault(a, set()).add(b)
    seen: set[str] = set()
    stack = list(children.get(node, ()))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(children.get(cur, ()))
    return seen


def _simple_paths(
    adj: dict[str, set[str]], src: str, dst: str, max_len: int, max_paths: int
) -> tuple[list[list[str]], bool]:
    """Enumerate simple src->dst paths over the undirected skeleton.

    Returns ``(paths, truncated)``. ``truncated`` is True if the ``max_paths``
    budget was hit — the caller must then fail closed (identification cannot be
    decided within budget) rather than trust a partial enumeration.
    """
    paths: list[list[str]] = []
    truncated = False

    def dfs(node: str, path: list[str]) -> None:
        nonlocal truncated
        if truncated or len(path) > max_len:
            return
        if node == dst:
            paths.append(list(path))
            if len(paths) > max_paths:
                truncated = True
            return
        for nxt in sorted(adj.get(node, ())):
            if truncated:
                return
            if nxt not in path:
                path.append(nxt)
                dfs(nxt, path)
                path.pop()

    dfs(src, [src])
    return paths, truncated


def _is_collider(directed: set[tuple[str, str]], prev: str, node: str, nxt: str) -> bool:
    # node is a collider on ...prev - node - nxt... iff both edges point INTO node.
    return (prev, node) in directed and (nxt, node) in directed


# --------------------------------------------------------------------------- #
# Identification.
# --------------------------------------------------------------------------- #

def identify(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    estimand: Estimand,
    *,
    latents: "frozenset[str] | set[str]" = frozenset(),
    allow_assumptions: "frozenset[str] | set[str]" = frozenset(),
    max_path_length: int = 12,
    max_paths: int = 2000,
) -> IdentificationResult:
    """Attempt backdoor identification of ``estimand`` against the graph.

    ``latents`` are node ids that are *unobserved* (cannot be adjusted for).
    ``allow_assumptions`` may contain ``NO_UNOBSERVED_CONFOUNDING`` to permit an
    identified-under-assumption result instead of a refusal.
    """
    t, y = estimand.treatment, estimand.outcome
    latents = set(latents)
    eid = estimand.id

    # Align the identification graph with the graph the solver would actually run:
    # propagate() drops self-loops, edges whose endpoints are not declared
    # hypotheses, and unwarranted edges. Governance must be evaluated on that same
    # effective graph, or the gate can permit/refuse a scenario the solver treats
    # differently.
    hyp_ids = {h.id for h in hypotheses}
    admissible = [
        e for e in edges
        if e.from_ref != e.to_ref
        and (not hyp_ids or (e.from_ref in hyp_ids and e.to_ref in hyp_ids))
        and e.warrant_refs
    ]
    directed = _directed(admissible)
    adj = _neighbours(directed)

    if t not in adj or y not in adj:
        return IdentificationResult(
            outcome=IdentificationOutcome.NOT_IDENTIFIED,
            estimand_id=eid,
            rationale=f"treatment {t!r} or outcome {y!r} not present in the admissible graph",
        )

    descendants_t = _descendants(directed, t)

    all_paths, truncated = _simple_paths(adj, t, y, max_path_length, max_paths)
    if truncated:
        # Fail closed: we could not enumerate the backdoor structure within budget,
        # so we cannot certify identifiability. Refuse rather than guess.
        return IdentificationResult(
            outcome=IdentificationOutcome.NOT_IDENTIFIED,
            estimand_id=eid,
            rationale=(
                "identification budget exceeded (graph too dense to enumerate "
                "backdoor paths within max_paths); refused rather than guessed"
            ),
        )

    # First pass: find backdoor paths and every collider on them. Conditioning on a
    # collider (or any descendant of one) opens the path it sits on, so those nodes
    # can never be valid adjustment candidates — even if they lie on a different,
    # otherwise-blockable backdoor path.
    backdoor: list[list[str]] = []
    collider_nodes: set[str] = set()
    for path in all_paths:
        if len(path) < 2:
            continue
        if (path[1], t) not in directed:
            continue  # not a backdoor path (first edge points out of treatment)
        backdoor.append(path)
        for i in range(1, len(path) - 1):
            if _is_collider(directed, path[i - 1], path[i], path[i + 1]):
                collider_nodes.add(path[i])
    collider_closure: set[str] = set(collider_nodes)
    for c in collider_nodes:
        collider_closure |= _descendants(directed, c)

    adjustment: set[str] = set()
    open_unblockable: list[tuple[str, ...]] = []
    latent_needed: set[str] = set()

    for path in backdoor:
        internal = path[1:-1]
        has_collider = any(
            _is_collider(directed, path[i - 1], path[i], path[i + 1])
            for i in range(1, len(path) - 1)
        )
        if has_collider:
            # An unconditioned collider blocks the path; we never condition on a
            # collider or its descendants (excluded below), so it stays blocked.
            continue

        # Open, collider-free backdoor path: block it by conditioning on a
        # non-collider that is observed, not a descendant of the treatment, and not
        # in the collider closure (so conditioning cannot open another path).
        blockers = [
            v for v in internal
            if v not in latents
            and v not in descendants_t
            and v not in collider_closure
            and v != y
        ]
        if blockers:
            adjustment.add(sorted(blockers)[0])
        else:
            open_unblockable.append(tuple(path))
            latent_needed.update(v for v in internal if v in latents)

    if not open_unblockable:
        return IdentificationResult(
            outcome=IdentificationOutcome.IDENTIFIED,
            estimand_id=eid,
            adjustment_set=tuple(sorted(adjustment)),
            rationale="backdoor criterion satisfied by an observed adjustment set",
        )

    if NO_UNOBSERVED_CONFOUNDING in set(allow_assumptions):
        return IdentificationResult(
            outcome=IdentificationOutcome.IDENTIFIED_UNDER_ASSUMPTION,
            estimand_id=eid,
            adjustment_set=tuple(sorted(adjustment)),
            assumptions=(NO_UNOBSERVED_CONFOUNDING,),
            blocking_paths=tuple(open_unblockable),
            required_measurements=tuple(sorted(latent_needed)),
            epistemic_penalty=1,
            rationale=(
                "identified only under the named assumption; the open backdoor "
                "path(s) are unblockable with observed variables"
            ),
        )

    return IdentificationResult(
        outcome=IdentificationOutcome.NOT_IDENTIFIED,
        estimand_id=eid,
        blocking_paths=tuple(open_unblockable),
        required_measurements=tuple(sorted(latent_needed)),
        rationale=(
            "not identified: open backdoor path(s) cannot be blocked by any "
            "observed variable; measure the required node(s) to identify it"
        ),
    )


def run_scenario(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    estimand: Estimand,
    *,
    latents: "frozenset[str] | set[str]" = frozenset(),
    allow_assumptions: "frozenset[str] | set[str]" = frozenset(),
    source_value: float = 1.0,
) -> ScenarioResult:
    """Two-layer gate: identify (governance) THEN, only if identified, solve
    (execution). An unidentified estimand is refused — no point estimate."""
    hyps = list(hypotheses)
    edge_list = list(edges)
    ident = identify(
        hyps, edge_list, estimand,
        latents=latents, allow_assumptions=allow_assumptions,
    )

    if not ident.identified:
        # REFUSAL. The solver is never invoked.
        return ScenarioResult(
            estimand_id=ident.estimand_id,
            modal_class=estimand.modal_class,
            identification=ident,
            refused=True,
            point_estimate=None,
            required_measurements=ident.required_measurements,
            blocking_paths=ident.blocking_paths,
            rationale=ident.rationale,
        )

    # Identified (possibly under assumption): the solver may run.
    prop = propagate(hyps, edge_list, estimand.treatment, estimand.outcome, source_value=source_value)
    estimate = sum(p.contribution for p in prop.paths) if prop.paths else 0.0
    return ScenarioResult(
        estimand_id=ident.estimand_id,
        modal_class=estimand.modal_class,
        identification=ident,
        refused=False,
        point_estimate=estimate,
        required_measurements=ident.required_measurements,
        blocking_paths=ident.blocking_paths,
        rationale=ident.rationale,
        witnessed_paths=list(prop.paths),
    )


# --------------------------------------------------------------------------- #
# Serialization boundary — the exposed route (consumed by the CLI).
# --------------------------------------------------------------------------- #

def result_to_dict(scenario: ScenarioResult) -> dict:
    """JSON-serializable view of a ScenarioResult, provenance-friendly."""
    ident = scenario.identification
    return {
        "estimandId": scenario.estimand_id,
        "modalClass": scenario.modal_class.value,
        "refused": scenario.refused,
        "pointEstimate": scenario.point_estimate,
        "requiredMeasurements": list(scenario.required_measurements),
        "blockingPaths": [list(p) for p in scenario.blocking_paths],
        "rationale": scenario.rationale,
        "identification": {
            "outcome": ident.outcome.value,
            "adjustmentSet": list(ident.adjustment_set),
            "assumptions": list(ident.assumptions),
            "epistemicPenalty": ident.epistemic_penalty,
        },
    }


def scenario_from_document(doc: dict) -> dict:
    """Run a causal scenario from a JSON document and return a serializable result.

    Document shape::

        {
          "hypotheses": [ {id, graphRef, label, ...}, ... ],
          "edges":      [ {id, graphRef, fromRef, toRef, sign, warrantRefs, ...}, ... ],
          "estimand":   {"treatment": "T", "outcome": "Y",
                         "query": "ate", "modalClass": "interventional"},
          "latents":          ["U", ...],
          "allowAssumptions": ["no-unobserved-confounding", ...]
        }

    This is the exposed route: it gates the solver on identification and never
    returns a point estimate for an unidentified estimand.
    """
    if not isinstance(doc, dict):
        raise ValueError("scenario document must be a JSON object")
    ed = doc.get("estimand")
    if not isinstance(ed, dict):
        raise ValueError("scenario document must contain an 'estimand' object")
    for key in ("treatment", "outcome"):
        if not ed.get(key):
            raise ValueError(f"estimand must declare a non-empty {key!r}")

    hyps = [Hypothesis.from_dict(d) for d in doc.get("hypotheses", [])]
    edges = [Edge.from_dict(d) for d in doc.get("edges", [])]
    graph_ref = ed.get("graphRef") or doc.get("graphRef") or (hyps[0].graph_ref if hyps else "")
    estimand = Estimand(
        graph_ref=graph_ref,
        treatment=ed["treatment"],
        outcome=ed["outcome"],
        query=ed.get("query", "ate"),
        modal_class=ModalClass(ed.get("modalClass", ModalClass.INTERVENTIONAL.value)),
    )
    scenario = run_scenario(
        hyps, edges, estimand,
        latents=frozenset(doc.get("latents", ())),
        allow_assumptions=frozenset(doc.get("allowAssumptions", ())),
    )
    return result_to_dict(scenario)
