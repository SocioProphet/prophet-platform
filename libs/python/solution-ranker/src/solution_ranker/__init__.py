"""Walk the MeshActionRegistry for ABB slot fillers and rank them into a SolutionShortlist.

The move this makes possible: Michael says *"we have a few options — do you already have a
model?"* instead of silently auto-routing to whatever scored highest. Zurich's Damian does the
former in its script and the latter in its architecture; the gap between those is where a
user loses the ability to see what was almost chosen.

The pipeline:

    intent set  ──►  ABB requirement  ──►  MAR walk (implementsAbb)  ──►  filter  ──►  rank
                                                                            │
                                              trust floor ────────────────►─┤
                                              access grade ──────────────►──┤
                                              counter-test ─────────────►───┘

Filtering happens BEFORE ranking, deliberately. A candidate below the trust floor is not a
low-ranked option, it is not an option — ranking it would put it on screen where a user could
pick it. Same for a denied access grade.

Auto-route is the narrowest possible claim: top-2 gap over threshold AND counter-test
confirmed AND access granted AND at least two candidates to compare. Anything less returns
`user-pick`, and `abstain` when there is nothing to offer. Those three states are the whole
API surface — there is no boolean "did it route".

Composes with:
  - ``access_prewalk`` (prophet-platform) for the access grade
  - sourceos-spec ``ArchitecturalBuildingBlock`` + ``MeshActionRegistry.implementsAbb``
  - prophet-mesh ``specs/solution-shortlist.schema.json`` for the emitted shape
  - Noetica's counter-test gate (#570) for ``counterTestStatus``
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Sequence

__all__ = [
    "CounterTestStatus", "RouteDecision", "AUTO_ROUTE_GAP_THRESHOLD",
    "Participant", "Candidate", "Shortlist",
    "rank_candidates", "build_shortlist", "canonical_json",
]

CounterTestStatus = Literal["confirmed", "available", "unavailable"]
RouteDecision = Literal["auto-route", "user-pick", "abstain"]

#: Mirrors prophet_mesh.solution_shortlist.AUTO_ROUTE_GAP_THRESHOLD. Pinned in both places
#: and asserted equal by test, so a policy change in one repo cannot silently diverge from
#: the other — two services that both believe they gate at the same threshold, gating
#: differently, is exactly the drift the shared-vector discipline exists to catch.
AUTO_ROUTE_GAP_THRESHOLD = 0.15


@dataclass(frozen=True)
class Participant:
    """One MeshActionRegistry participant, as far as ranking cares.

    ``implements_abb`` is the CLAIM the registry carries — verifying that the participant
    actually satisfies the ABB's protocol is the consumer's job, not the registry's (see
    sourceos-spec#224). ``protocol_verified`` records whether that verification ran; an
    unverified claim can still be shortlisted, but it cannot auto-route.
    """

    repo: str
    implements_abb: tuple[str, ...] = ()
    trust_score: float = 0.0
    catalog_verbs: tuple[str, ...] = ()
    counter_test_status: CounterTestStatus = "unavailable"
    counter_test_ref: str | None = None
    protocol_verified: bool = False


@dataclass(frozen=True)
class Candidate:
    repo: str
    score: float
    match_reason: tuple[str, ...]
    counter_test_status: CounterTestStatus
    counter_test_ref: str | None
    access_grade: str
    access_reason: str
    remediation_url: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "participantRef": self.repo,
            "score": round(self.score, 4),
            "matchReason": list(self.match_reason),
            "counterTestStatus": self.counter_test_status,
            "accessDecision": {"grade": self.access_grade},
        }
        if self.counter_test_ref:
            out["counterTestRef"] = self.counter_test_ref
        if self.remediation_url:
            out["accessDecision"]["remediation"] = {
                "url": self.remediation_url,
                "expectedReturn": "ArtifactConsentRecord",
            }
        return out


@dataclass
class Shortlist:
    candidates: list[Candidate]
    decision: RouteDecision
    decision_reason: str
    chosen_index: int | None
    empty_reason: str | None
    #: Participants filtered out BEFORE ranking, with why. Not decoration: a caller asking
    #: "why isn't X here" must get an answer, and an unexplained absence is indistinguishable
    #: from a walk that never saw X.
    excluded: list[tuple[str, str]] = field(default_factory=list)

    def to_json(self, *, abb: str | None, mar_digest: str, catalog_digest: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schemaVersion": "0.1.0",
            "kind": "SolutionShortlist",
            "shortlist": [c.to_json() for c in self.candidates],
            "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "derivedFrom": {"marDigest": mar_digest, "abbCatalogDigest": catalog_digest},
        }
        if abb:
            out["abbRequirement"] = abb
        if self.empty_reason:
            out["emptyReason"] = self.empty_reason
        else:
            verdict: dict[str, Any] = {"decision": self.decision, "reason": self.decision_reason}
            if self.chosen_index is not None:
                verdict["chosenIndex"] = self.chosen_index
            out["autoRouteVerdict"] = verdict
        return out


def rank_candidates(
    participants: Sequence[Participant],
    *,
    abb: str | None,
    intent_verbs: Sequence[str],
    min_trust: float,
    access_grader,
) -> tuple[list[Candidate], list[tuple[str, str]]]:
    """Filter then rank. Returns ``(candidates, excluded)``.

    ``access_grader`` is injected rather than imported so this lib does not hard-depend on
    access-prewalk — a caller can supply a stub in tests, and a different estate can supply a
    different grader. It takes a repo id and returns ``(grade, reason, remediation_url)``.

    Exclusions are RECORDED, not dropped. Three reasons a participant never reaches ranking:
      - it does not claim the required ABB (not a candidate at all)
      - its trust score is below the floor (the ledger's judgement is a gate, not a penalty)
      - access is denied (offering it would put an unusable option on screen)

    A `requires-consent` candidate IS ranked — that is the grade whose whole purpose is to be
    shown with a path forward.
    """
    candidates: list[Candidate] = []
    excluded: list[tuple[str, str]] = []

    for p in participants:
        if abb and abb not in p.implements_abb:
            excluded.append((p.repo, f"does not claim {abb} in implementsAbb"))
            continue

        if p.trust_score < min_trust:
            excluded.append((
                p.repo,
                f"trust {p.trust_score:.2f} below floor {min_trust:.2f} — the ledger's "
                f"judgement gates candidacy; a low-trust option must not be rankable",
            ))
            continue

        grade, access_reason, remediation = access_grader(p.repo)
        if grade == "denied":
            excluded.append((p.repo, f"access denied: {access_reason}"))
            continue

        reasons: list[str] = []
        overlap = sorted(set(intent_verbs) & set(p.catalog_verbs))
        if overlap:
            reasons.append(f"verb overlap {overlap} between intent set and participant catalogue")
        if abb:
            reasons.append(
                f"{abb} claim {'VERIFIED against protocol' if p.protocol_verified else 'declared but unverified'}"
            )
        reasons.append(f"trust {p.trust_score:.2f} clears floor {min_trust:.2f}")

        # Score: verb coverage x trust, penalised when the ABB claim was never verified.
        # An unverified claim is not disqualifying (it still shows) but it must not outrank
        # a verified one on equal evidence — the registry establishes the claim, not its truth.
        coverage = (len(overlap) / len(intent_verbs)) if intent_verbs else 0.5
        verification_factor = 1.0 if (p.protocol_verified or not abb) else 0.8
        consent_factor = 1.0 if grade == "granted" else 0.85
        score = coverage * p.trust_score * verification_factor * consent_factor

        candidates.append(Candidate(
            repo=p.repo, score=score, match_reason=tuple(reasons),
            counter_test_status=p.counter_test_status, counter_test_ref=p.counter_test_ref,
            access_grade=grade, access_reason=access_reason, remediation_url=remediation,
        ))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates, excluded


def build_shortlist(
    participants: Sequence[Participant],
    *,
    abb: str | None,
    intent_verbs: Sequence[str],
    min_trust: float,
    access_grader,
    counter_test_required: bool = True,
) -> Shortlist:
    """Produce the full shortlist including the route decision.

    The route decision is the narrowest claim the evidence supports:

      abstain     nothing to offer — every participant was excluded, or none claimed the ABB
      user-pick   candidates exist but auto-route's preconditions are not all met
      auto-route  top-2 gap > threshold AND counter-test confirmed AND access granted
                  AND at least 2 candidates

    Every path to `user-pick` states WHICH precondition failed. "Not confident enough" is not
    a reason a user can act on; "the runner-up scored within 0.04" is.
    """
    candidates, excluded = rank_candidates(
        participants, abb=abb, intent_verbs=intent_verbs,
        min_trust=min_trust, access_grader=access_grader,
    )

    if not candidates:
        why = "; ".join(f"{r}: {reason}" for r, reason in excluded) or "no participants supplied"
        return Shortlist(
            candidates=[], decision="abstain",
            decision_reason="no candidate survived filtering",
            chosen_index=None,
            empty_reason=(
                f"no participant is a viable filler for {abb or 'this intent'}. Excluded: {why}"
            ),
            excluded=excluded,
        )

    top = candidates[0]

    if len(candidates) < 2:
        return Shortlist(
            candidates=candidates, decision="user-pick",
            decision_reason=(
                "only one candidate — with nothing to compare against, the top-2 gap is "
                "undefined and 'auto' would be the caller's default rather than a measured "
                "decision"
            ),
            chosen_index=None, empty_reason=None, excluded=excluded,
        )

    gap = top.score - candidates[1].score
    blockers: list[str] = []
    if gap < AUTO_ROUTE_GAP_THRESHOLD:
        blockers.append(
            f"top-2 gap {gap:.3f} is under the {AUTO_ROUTE_GAP_THRESHOLD} threshold "
            f"({top.repo} {top.score:.3f} vs {candidates[1].repo} {candidates[1].score:.3f})"
        )
    if counter_test_required and top.counter_test_status != "confirmed":
        blockers.append(
            f"top candidate's counter-test is '{top.counter_test_status}', not 'confirmed'"
        )
    if top.access_grade != "granted":
        blockers.append(f"top candidate's access is '{top.access_grade}', not 'granted'")

    if blockers:
        return Shortlist(
            candidates=candidates, decision="user-pick",
            decision_reason="; ".join(blockers), chosen_index=None,
            empty_reason=None, excluded=excluded,
        )

    return Shortlist(
        candidates=candidates, decision="auto-route",
        decision_reason=(
            f"top candidate {top.repo} scored {top.score:.3f}, "
            f"{gap:.3f} clear of the runner-up (>{AUTO_ROUTE_GAP_THRESHOLD}); "
            f"counter-test confirmed; access granted"
        ),
        chosen_index=0, empty_reason=None, excluded=excluded,
    )


def canonical_json(obj: Any) -> str:
    """Canonical JSON — recursive key sort, no whitespace, non-ASCII RAW.

    ``ensure_ascii=False`` matches lawful-verdict and the TypeScript canonicaliser. The
    default would escape non-ASCII and every digest over accented content would diverge
    between languages (the bug caught in review on #1065).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
