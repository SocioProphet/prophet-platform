"""Backward reasoning (abduction) over CausalHypothesis / CausalEdge.

The surpass move IBM's HOPE-Graph slide explicitly deferred: given a target
hypothesis whose value moved (e.g. `Revenue` fell), rank the warrant-backed
causal paths that could explain the move. Sibling of the forward propagator
in `causal_graph.py`; the two share the ingest layer, the invariant enforcer,
and the refusal properties.

What abduction returns is NOT a scalar likelihood — it is a **list of
ranked candidate explanations**, each a path from some source hypothesis to
the observed target, scored by the same signed weight × confidence product
the forward propagator uses. The score sign matches the observed direction
(if revenue *fell*, an explanatory path must produce a *negative* net
contribution), so a paths_that_would_have_lifted_revenue does not appear as
a candidate for a revenue drop.

**Warrant-weighted ranking.** A path with a strong signed contribution but
thin warrants is ranked lower than a path with a comparable contribution and
richer warrants. Rationale: the whole session's doctrine is that unverified
weight is inadmissible; the same principle downstream means that between two
explanations of equal magnitude, the one an auditor can stand behind wins.

The `warrant_weight` argument controls that mix. Default 0.2 (20% of the
final score is warrant coverage, 80% is signed contribution magnitude);
extremes are documented rather than hidden. `warrant_weight=0` reproduces
the "pure magnitude" ranking a naive engine would emit and is deliberately
NOT the default.

Refusal properties inherited from `causal_graph.propagate`:
  * unwarranted edges cannot participate — they log as abstentions;
  * cycles refused mid-DFS with an abstention;
  * every ranked candidate is warrant-backed end-to-end;
  * per-path attribution is a list, not a scalar dressed as an answer.

Stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from open_ep_framework.causal_graph import (
    Edge,
    Hypothesis,
    Propagation,
    PathContribution,
    enforce_invariants,
    propagate,
)


@dataclass(frozen=True)
class AbductionCandidate:
    """One ranked explanation for an observed movement in a target hypothesis.

    Wraps a `PathContribution` from the forward propagator so every candidate
    is an already-attributed, already-warrant-backed path. Fields:

    - `source_id` — the origin hypothesis id an auditor names as the cause.
    - `contribution` — the signed magnitude the forward propagator would emit
      for this source→target path at `source_value=1.0`. Its sign is the
      predicted direction of effect on the target.
    - `warrant_coverage` — number of distinct warrant URNs supporting the
      path (an edge with three warrants counts three; the path with more
      independent evidence rates higher).
    - `score` — the ranked score, combining magnitude and warrant coverage
      per `warrant_weight`. Kept alongside contribution so a caller can
      always distinguish "big effect, thin evidence" from "small effect,
      thick evidence".
    """
    source_id: str
    target_id: str
    contribution: float
    combined_confidence: float
    warrant_coverage: int
    score: float
    hypothesis_path: tuple[str, ...]
    edge_path: tuple[str, ...]
    all_warrants: tuple[str, ...]


@dataclass
class Abduction:
    """Result of abducing explanations for one observed movement in a target.

    `candidates` is ordered highest-score first. `abstentions` and
    `invariant_errors` follow the same shape as `Propagation` so consumers
    that already handle the forward result handle this one too.
    """
    target_id: str
    observed_sign: str                  # "positive" | "negative" | "either"
    candidates: list[AbductionCandidate] = field(default_factory=list)
    abstentions: list[str] = field(default_factory=list)
    invariant_errors: list[object] = field(default_factory=list)


def _sign_matches(contribution: float, observed_sign: str, eps: float = 1e-9) -> bool:
    if observed_sign == "either":
        return abs(contribution) > eps
    if observed_sign == "positive":
        return contribution > eps
    if observed_sign == "negative":
        return contribution < -eps
    raise ValueError(f"invalid observed_sign {observed_sign!r}; expected positive|negative|either")


def _score_path(path: PathContribution, warrant_weight: float) -> tuple[float, int]:
    """Combine signed magnitude and warrant coverage into a single rank score.

    Returned in the shape the caller wants (score, warrant_coverage) so both
    are available for the AbductionCandidate without recomputing.
    """
    coverage = len(set(path.all_warrants))
    if warrant_weight < 0.0 or warrant_weight > 1.0:
        raise ValueError(f"warrant_weight {warrant_weight} outside [0,1]")
    # Coverage is diminishing-returns via a linear ratio that SATURATES at 4:
    # 0 warrants → 0.00, 1 → 0.25, 2 → 0.50, 3 → 0.75, and 4+ all → 1.00. So
    # the 5th warrant is worth the same as the 4th, and the 2nd is worth
    # the same as the 3rd. Deliberate: it keeps the score bounded to [0,1]
    # (the same domain as contract `weight` and `confidence`), and it makes
    # the ranking behaviour transparent — 4 was picked so a hypothesis with
    # multiple independent sources beats one with a single citation, without
    # rewarding warrant-count arms races. A caller can inspect
    # `warrant_coverage` directly for raw counts.
    coverage_score = min(1.0, coverage / 4.0)   # saturates at 4 distinct warrants
    magnitude = min(1.0, abs(path.contribution))
    score = (1.0 - warrant_weight) * magnitude + warrant_weight * coverage_score
    return round(score, 4), coverage


def abduce(
    hypotheses: Iterable[Hypothesis],
    edges: Iterable[Edge],
    target_id: str,
    *,
    observed_sign: str = "either",
    warrant_weight: float = 0.2,
    top_k: int | None = 10,
    candidate_source_ids: Iterable[str] | None = None,
) -> Abduction:
    """Rank warrant-backed causal paths that could explain the observed move.

    Iterates every hypothesis in the graph (or the caller-supplied
    `candidate_source_ids`), runs the forward propagator to that target from
    each, filters to paths whose contribution sign matches `observed_sign`,
    and returns them ordered by combined score.

    `top_k=None` returns all matching candidates. Default 10 keeps the
    response cockpit-sized; a caller doing bulk analytics can override.

    Validates arguments up front: an invalid `observed_sign` /
    `warrant_weight` / `top_k` raises before any traversal happens, so a
    caller with a degenerate graph still gets a fast, honest error rather
    than a silent empty result.
    """
    # Argument validation runs first so bad inputs cannot be masked by a
    # graph that produces no candidates. `_sign_matches` and `_score_path`
    # both validate too, but reaching them requires at least one path.
    if observed_sign not in ("positive", "negative", "either"):
        raise ValueError(f"invalid observed_sign {observed_sign!r}; expected positive|negative|either")
    if not (0.0 <= warrant_weight <= 1.0):
        raise ValueError(f"warrant_weight {warrant_weight} outside [0,1]")
    if top_k is not None:
        # Guard non-int (e.g. 1.5, "5", True) up front. Type-hints say int|None;
        # without an isinstance check a float slips through the < 1 comparison
        # and later dies in list slicing with TypeError, and a string raises
        # TypeError inside the comparison itself. Either way, not a clean
        # ValueError. bool is a subclass of int in Python — exclude it explicitly
        # since top_k=True would otherwise pass as 1.
        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise ValueError(f"top_k must be an int (or None); got {type(top_k).__name__}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1 or None; got {top_k}")

    hyps = list(hypotheses)
    edge_list = list(edges)

    result = Abduction(target_id=target_id, observed_sign=observed_sign)
    result.invariant_errors = enforce_invariants(hyps, edge_list)

    by_id = {h.id: h for h in hyps}
    if target_id not in by_id:
        result.abstentions.append(f"target {target_id} not declared in hypothesis set")
        return result

    sources = list(candidate_source_ids) if candidate_source_ids is not None else [
        h.id for h in hyps if h.id != target_id
    ]

    for source_id in sources:
        if source_id not in by_id:
            result.abstentions.append(f"candidate source {source_id} not declared; skipped")
            continue
        prop: Propagation = propagate(hyps, edge_list, source_id, target_id)
        # Bubble any non-endpoint abstentions up so the caller sees the whole
        # picture (unwarranted edges, cycles). Missing-endpoint chatter would
        # be noisy — we already checked source resolution above.
        for note in prop.abstentions:
            if "not declared in hypothesis set" in note:
                continue
            result.abstentions.append(f"[{source_id}] {note}")

        for path in prop.paths:
            if not _sign_matches(path.contribution, observed_sign):
                continue
            score, coverage = _score_path(path, warrant_weight)
            result.candidates.append(AbductionCandidate(
                source_id=source_id, target_id=target_id,
                contribution=path.contribution,
                combined_confidence=path.combined_confidence,
                warrant_coverage=coverage,
                score=score,
                hypothesis_path=path.hypothesis_path,
                edge_path=path.edge_path,
                all_warrants=path.all_warrants,
            ))

    # Deterministic ordering: score desc, then |contribution| desc, then source_id asc.
    result.candidates.sort(
        key=lambda c: (-c.score, -abs(c.contribution), c.source_id, c.edge_path),
    )
    if top_k is not None:
        result.candidates = result.candidates[:top_k]

    if not result.candidates:
        result.abstentions.append(
            f"no warrant-backed path to {target_id} with sign {observed_sign} found"
        )
    return result
