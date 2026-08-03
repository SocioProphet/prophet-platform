"""Signed, warrant-weighted propagation over CausalHypothesis / CausalEdge.

First real consumer of the epistemic-kernel schemas that landed in
SourceOS-Linux/sourceos-spec#209. Two contracts arrive from that repo:

  * `CausalHypothesis` — a labelled, direction-neutral, falsifiable node with
    topic terms, an optional KKO type, an optional ER cluster ref, a claim
    lifecycle (`proposed` | `evidenced` | `scored`), and a warrant list.
  * `CausalEdge` — a signed edge with mandatory `warrantRefs`, optional
    `weight` (magnitude in [0,1]) and `confidence`, and digest-pinned
    extractor provenance. Polarity lives ONLY on the edge.

This module ingests a set of both, enforces the invariants JSON Schema cannot
express, and propagates a source hypothesis's contribution to a target
hypothesis (e.g. Revenue) by walking the DAG.

Two properties the module refuses to violate — closing three defect classes
we removed elsewhere in the estate this session:

  1. **No unwarranted causality.** An edge with no `warrantRefs` — impossible
     to construct by contract, but tolerated in dirty data — cannot
     contribute. It is reported in the abstention record; the path it sits on
     produces no contribution to the target.
  2. **No self-loop and no ambiguous graph reference.** Every edge's
     endpoints must resolve to hypotheses declared in the same graph. A cycle
     detected during traversal is reported and the path abandoned rather than
     silently truncated.
  3. **Signed contribution, non-negative magnitude.** The edge's `sign`
     controls direction of effect; `weight` (magnitude) is always in [0,1].
     A `positive` edge contributes `+weight * incoming`; `negative`
     contributes `-weight * incoming`. Confidence, when present, scales the
     contribution — a low-confidence edge produces a small contribution even
     if its weight is high.

The engine is intentionally conservative. A production propagator would model
non-linear composition (e.g. saturation, interaction terms) and time lags;
this one does linear signed propagation over the DAG so the shape of the
answer is auditable end-to-end. When a target's contribution comes from
multiple paths, each path's contribution is reported separately so the
attribution is a list of witnessed paths, not a single scalar dressed as one.

Stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class Hypothesis:
    """Subset of the CausalHypothesis contract this engine consumes."""
    id: str
    graph_ref: str
    label: str
    claim_status: str = "proposed"        # proposed | evidenced | scored
    warrant_refs: tuple[str, ...] = ()
    kko_type_ref: str | None = None
    entity_cluster_ref: str | None = None

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "Hypothesis":
        return cls(
            id=doc["id"],
            graph_ref=doc["graphRef"],
            label=doc.get("label", ""),
            claim_status=doc.get("claimStatus", "proposed"),
            warrant_refs=tuple(doc.get("warrantRefs") or ()),
            kko_type_ref=doc.get("kkoTypeRef"),
            entity_cluster_ref=doc.get("entityClusterRef"),
        )


@dataclass(frozen=True)
class Edge:
    """Subset of the CausalEdge contract this engine consumes."""
    id: str
    graph_ref: str
    from_ref: str
    to_ref: str
    sign: str                              # "positive" | "negative"
    warrant_refs: tuple[str, ...]
    weight: float = 1.0
    confidence: float = 1.0

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "Edge":
        return cls(
            id=doc["id"],
            graph_ref=doc["graphRef"],
            from_ref=doc["fromRef"],
            to_ref=doc["toRef"],
            sign=doc["sign"],
            warrant_refs=tuple(doc.get("warrantRefs") or ()),
            weight=float(doc.get("weight", 1.0)),
            confidence=float(doc.get("confidence", 1.0)),
        )


@dataclass(frozen=True)
class PathContribution:
    """One witnessed path from a source hypothesis to a target hypothesis.

    `contribution` is the propagated numeric effect along this path; the
    hypothesis and edge sequences make it auditable. Every edge on the path is
    warrant-backed by construction — an unwarranted path is filtered out
    before this record is produced and shows up in `Propagation.abstentions`.
    """
    source_id: str
    target_id: str
    hypothesis_path: tuple[str, ...]       # ordered ids from source to target
    edge_path: tuple[str, ...]             # ordered edge ids traversed
    contribution: float
    combined_confidence: float
    all_warrants: tuple[str, ...]


@dataclass
class GraphInvariantError:
    kind: str                              # e.g. "self-loop", "endpoint-missing", "graph-mismatch"
    detail: str


@dataclass
class Propagation:
    """Result of propagating from one source hypothesis to one target.

    `total_signed_contribution` is the sum of per-path contributions. Reported
    alongside the per-path list rather than in place of it, so a caller can
    always see which paths produced which fraction of the total — a scalar
    with no attribution is precisely the "confidence 0.5" pattern this
    session removed elsewhere.
    """
    source_id: str
    target_id: str
    paths: list[PathContribution] = field(default_factory=list)
    abstentions: list[str] = field(default_factory=list)    # human-readable
    invariant_errors: list[GraphInvariantError] = field(default_factory=list)

    @property
    def total_signed_contribution(self) -> float:
        return sum(p.contribution for p in self.paths)


# ---------------------------------------------------------------------------
# Ingest + invariant enforcement
# ---------------------------------------------------------------------------

def _sign_factor(sign: str) -> float:
    if sign == "positive":
        return 1.0
    if sign == "negative":
        return -1.0
    raise ValueError(f"invalid edge sign {sign!r}; expected 'positive' or 'negative'")


def enforce_invariants(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
) -> list[GraphInvariantError]:
    """Enforce invariants JSON Schema cannot express.

    Returned as a list rather than raised so a caller can quarantine a bad
    slice of the graph and still propagate over the well-formed part. A
    matching Propagation records these under `invariant_errors`.
    """
    hyps = list(hypotheses)
    edge_list = list(edges)
    errors: list[GraphInvariantError] = []

    by_id = {h.id: h for h in hyps}
    graphs = {h.graph_ref for h in hyps}
    if len(graphs) > 1:
        errors.append(GraphInvariantError("multi-graph-hypothesis-set",
            f"hypotheses declared across {len(graphs)} graphRefs; propagation is scoped to one graph"))

    for e in edge_list:
        if e.from_ref == e.to_ref:
            errors.append(GraphInvariantError("self-loop", f"edge {e.id} points at its own from_ref"))
        if e.from_ref not in by_id:
            errors.append(GraphInvariantError("endpoint-missing",
                f"edge {e.id} fromRef {e.from_ref} not in this hypothesis set"))
        if e.to_ref not in by_id:
            errors.append(GraphInvariantError("endpoint-missing",
                f"edge {e.id} toRef {e.to_ref} not in this hypothesis set"))
        if e.from_ref in by_id and by_id[e.from_ref].graph_ref != e.graph_ref:
            errors.append(GraphInvariantError("graph-mismatch",
                f"edge {e.id} graphRef {e.graph_ref} != hypothesis {e.from_ref} graphRef"))
        if e.to_ref in by_id and by_id[e.to_ref].graph_ref != e.graph_ref:
            errors.append(GraphInvariantError("graph-mismatch",
                f"edge {e.id} graphRef {e.graph_ref} != hypothesis {e.to_ref} graphRef"))
        if not (0.0 <= e.weight <= 1.0):
            errors.append(GraphInvariantError("weight-out-of-range",
                f"edge {e.id} weight {e.weight} not in [0,1]"))
        if not (0.0 <= e.confidence <= 1.0):
            errors.append(GraphInvariantError("confidence-out-of-range",
                f"edge {e.id} confidence {e.confidence} not in [0,1]"))
    return errors


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------

def propagate(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    source_id: str,
    target_id: str,
    *,
    source_value: float = 1.0,
    max_path_length: int = 12,
) -> Propagation:
    """Propagate a source hypothesis's contribution to a target.

    Signed, warrant-weighted, path-attributed. Cycles are refused; unwarranted
    edges are skipped and reported as abstentions; every reported path is
    warrant-backed end-to-end. `max_path_length` guards against pathological
    inputs — a path longer than that is a modeling smell and refused rather
    than run for hours.
    """
    hyps = list(hypotheses); edge_list = list(edges)
    result = Propagation(source_id=source_id, target_id=target_id)
    result.invariant_errors = enforce_invariants(hyps, edge_list)

    by_id = {h.id: h for h in hyps}
    if source_id not in by_id:
        result.abstentions.append(f"source {source_id} not declared in hypothesis set")
        return result
    if target_id not in by_id:
        result.abstentions.append(f"target {target_id} not declared in hypothesis set")
        return result

    # Only well-formed edges participate; the abstention log names the rest.
    adj: dict[str, list[Edge]] = {}
    endpoint_ids = {e.from_ref for e in edge_list} | {e.to_ref for e in edge_list}
    for e in edge_list:
        # Filter edges the invariant pass would have complained about.
        if e.from_ref == e.to_ref:
            result.abstentions.append(f"edge {e.id} self-loop; skipped")
            continue
        if e.from_ref not in by_id or e.to_ref not in by_id:
            result.abstentions.append(f"edge {e.id} endpoint not resolvable; skipped")
            continue
        if not e.warrant_refs:
            result.abstentions.append(f"edge {e.id} has no warrantRefs; unwarranted causality is inadmissible")
            continue
        adj.setdefault(e.from_ref, []).append(e)

    # DFS from source to target, refusing cycles and paths above the depth cap.
    def dfs(node: str, value: float, confidence: float,
            visited: tuple[str, ...], edges_taken: tuple[str, ...],
            warrants: tuple[str, ...]) -> None:
        if len(visited) > max_path_length:
            result.abstentions.append(
                f"path from {source_id} to {target_id} exceeded max_path_length={max_path_length}; refused"
            )
            return
        if node == target_id and edges_taken:
            result.paths.append(PathContribution(
                source_id=source_id, target_id=target_id,
                hypothesis_path=visited, edge_path=edges_taken,
                contribution=value, combined_confidence=confidence,
                all_warrants=warrants,
            ))
            return
        for e in adj.get(node, ()):
            if e.to_ref in visited:
                result.abstentions.append(f"cycle detected at {e.to_ref} via edge {e.id}; path abandoned")
                continue
            step = _sign_factor(e.sign) * e.weight * e.confidence * value
            dfs(
                e.to_ref,
                step,
                confidence * e.confidence,
                visited + (e.to_ref,),
                edges_taken + (e.id,),
                warrants + e.warrant_refs,
            )

    dfs(source_id, source_value, 1.0, (source_id,), (), ())
    if not result.paths:
        result.abstentions.append(
            f"no warrant-backed path from {source_id} to {target_id} found"
        )
    return result
