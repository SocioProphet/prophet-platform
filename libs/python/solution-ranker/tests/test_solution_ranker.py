"""solution-ranker contract tests, plus the Eve Smith end-to-end scenario.

The invariants pinned here:

  1. Filtering happens BEFORE ranking — a below-floor or access-denied participant is not a
     low-ranked option, it is not an option. Ranking it would put it on screen where a user
     could pick it.
  2. Every exclusion is RECORDED with a reason. An unexplained absence is indistinguishable
     from a walk that never saw the participant.
  3. `auto-route` requires ALL of: gap > threshold, counter-test confirmed, access granted,
     >= 2 candidates. Each failure path names WHICH precondition blocked it — "not confident
     enough" is not a reason a user can act on.
  4. A `requires-consent` candidate IS ranked (that grade exists to be shown with a path
     forward) but cannot auto-route.
"""

from __future__ import annotations

import pytest

from solution_ranker import (
    AUTO_ROUTE_GAP_THRESHOLD,
    Participant,
    build_shortlist,
    canonical_json,
    digest,
    rank_candidates,
)

# A grader that grants everything — isolates ranking behaviour from access behaviour.
GRANT_ALL = lambda repo: ("granted", "no gate on this resource", None)
DENY_ALL = lambda repo: ("denied", "role missing and resource is not consentable", None)


def _p(repo: str, **kw) -> Participant:
    return Participant(**{
        "repo": repo, "implements_abb": ("ABB.03",), "trust_score": 0.80,
        "catalog_verbs": ("retrieve", "evaluate"), "counter_test_status": "confirmed",
        "counter_test_ref": f"urn:srcos:ctest:{repo}", "protocol_verified": True, **kw,
    })


# ── filter before rank ─────────────────────────────────────────────────────────

def test_below_trust_floor_is_EXCLUDED_not_low_ranked() -> None:
    """A low-trust option must not be rankable. If it were merely low-ranked it would still
    be on screen, and a user could pick what the ledger already judged untrustworthy."""
    cands, excluded = rank_candidates(
        [_p("org/good"), _p("org/untrusted", trust_score=0.10)],
        abb="ABB.03", intent_verbs=["retrieve"], min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert [c.repo for c in cands] == ["org/good"]
    assert any("org/untrusted" == r and "below floor" in why for r, why in excluded)


def test_access_denied_is_EXCLUDED_not_ranked() -> None:
    cands, excluded = rank_candidates(
        [_p("org/a")], abb="ABB.03", intent_verbs=["retrieve"],
        min_trust=0.45, access_grader=DENY_ALL,
    )
    assert cands == []
    assert any("access denied" in why for _, why in excluded)


def test_not_claiming_the_abb_is_EXCLUDED() -> None:
    cands, excluded = rank_candidates(
        [_p("org/db", implements_abb=("ABB.03",)), _p("org/other", implements_abb=("ABB.07",))],
        abb="ABB.03", intent_verbs=["retrieve"], min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert [c.repo for c in cands] == ["org/db"]
    assert any("does not claim ABB.03" in why for _, why in excluded)


def test_every_exclusion_carries_a_substantive_reason() -> None:
    """An unexplained absence is indistinguishable from a walk that never saw the participant.
    A caller asking 'why isn't X here' must get an answer."""
    _, excluded = rank_candidates(
        [
            _p("org/wrong-abb", implements_abb=("ABB.99",)),
            _p("org/low-trust", trust_score=0.01),
        ],
        abb="ABB.03", intent_verbs=["retrieve"], min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert len(excluded) == 2
    for repo, why in excluded:
        assert len(why) > 20, f"{repo}: reason too thin — {why!r}"


def test_requires_consent_IS_ranked_because_that_grade_exists_to_be_shown() -> None:
    """The grade whose entire purpose is 'not yet, but here's the path'. Excluding it would
    collapse it into denied — the exact thing the three-grade shape prevents."""
    grader = lambda repo: ("requires-consent", "missing billing-reader",
                           "https://consent.example/request?sig=abc")
    cands, excluded = rank_candidates(
        [_p("org/a")], abb="ABB.03", intent_verbs=["retrieve"],
        min_trust=0.45, access_grader=grader,
    )
    assert len(cands) == 1
    assert cands[0].access_grade == "requires-consent"
    assert cands[0].remediation_url is not None
    assert excluded == []


# ── scoring ────────────────────────────────────────────────────────────────────

def test_unverified_abb_claim_scores_below_a_verified_one_on_equal_evidence() -> None:
    """The registry establishes the CLAIM, not its truth (sourceos-spec#224). An unverified
    claim still shows — but must not outrank a verified one when the rest is equal."""
    cands, _ = rank_candidates(
        [_p("org/verified", protocol_verified=True), _p("org/declared", protocol_verified=False)],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert [c.repo for c in cands] == ["org/verified", "org/declared"]
    assert cands[0].score > cands[1].score
    assert any("VERIFIED" in r for r in cands[0].match_reason)
    assert any("unverified" in r for r in cands[1].match_reason)


def test_every_candidate_carries_at_least_one_match_reason() -> None:
    """A candidate with an unreadable reason is a candidate nobody should route to."""
    cands, _ = rank_candidates(
        [_p("org/a")], abb="ABB.03", intent_verbs=["retrieve"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert cands[0].match_reason
    for r in cands[0].match_reason:
        assert len(r) > 10


def test_candidates_are_sorted_descending_by_score() -> None:
    cands, _ = rank_candidates(
        [
            _p("org/low", trust_score=0.50, catalog_verbs=("retrieve",)),
            _p("org/high", trust_score=0.95, catalog_verbs=("retrieve", "evaluate")),
            _p("org/mid", trust_score=0.70, catalog_verbs=("retrieve", "evaluate")),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    scores = [c.score for c in cands]
    assert scores == sorted(scores, reverse=True)
    assert cands[0].repo == "org/high"


# ── the route decision ─────────────────────────────────────────────────────────

def test_auto_route_when_every_precondition_holds() -> None:
    s = build_shortlist(
        [
            _p("org/strong", trust_score=0.95, catalog_verbs=("retrieve", "evaluate")),
            _p("org/weak", trust_score=0.50, catalog_verbs=("retrieve",)),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "auto-route"
    assert s.chosen_index == 0
    assert "clear of the runner-up" in s.decision_reason


def test_narrow_gap_forces_user_pick_and_SAYS_the_gap() -> None:
    """'Not confident enough' is not a reason a user can act on. 'The runner-up scored within
    0.04' is."""
    s = build_shortlist(
        [_p("org/a", trust_score=0.80), _p("org/b", trust_score=0.79)],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "user-pick"
    assert "top-2 gap" in s.decision_reason
    assert "threshold" in s.decision_reason


def test_unconfirmed_counter_test_blocks_auto_route_and_names_it() -> None:
    """Per Noetica#570's counter-test gate."""
    s = build_shortlist(
        [
            _p("org/strong", trust_score=0.95, counter_test_status="available",
               catalog_verbs=("retrieve", "evaluate")),
            _p("org/weak", trust_score=0.50, catalog_verbs=("retrieve",)),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "user-pick"
    assert "counter-test" in s.decision_reason
    assert "available" in s.decision_reason


def test_requires_consent_top_blocks_auto_route() -> None:
    """A user must see and act on the remediation — Michael cannot silently route into a
    resource the user has not been granted."""
    grader = lambda repo: (("requires-consent", "missing billing-reader", "https://c/x")
                           if repo == "org/strong" else ("granted", "ok", None))
    s = build_shortlist(
        [
            _p("org/strong", trust_score=0.95, catalog_verbs=("retrieve", "evaluate")),
            _p("org/weak", trust_score=0.50, catalog_verbs=("retrieve",)),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=grader,
    )
    assert s.decision == "user-pick"
    assert "access is 'requires-consent'" in s.decision_reason


def test_single_candidate_is_user_pick_not_auto_route() -> None:
    """With nothing to compare against, the gap is undefined and 'auto' would be the caller's
    default rather than a measured decision."""
    s = build_shortlist(
        [_p("org/only")], abb="ABB.03", intent_verbs=["retrieve"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "user-pick"
    assert "only one candidate" in s.decision_reason


def test_no_survivors_is_abstain_with_an_empty_reason() -> None:
    """Empties are signal. An empty shortlist WITH a reason is a valid answer; without one it
    is indistinguishable from a broken walk."""
    s = build_shortlist(
        [_p("org/a", trust_score=0.01)], abb="ABB.03", intent_verbs=["retrieve"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "abstain"
    assert s.candidates == []
    assert s.empty_reason and "below floor" in s.empty_reason


def test_multiple_blockers_are_ALL_reported_not_just_the_first() -> None:
    """A caller fixing one blocker should not discover the next only on the retry."""
    s = build_shortlist(
        [
            _p("org/a", trust_score=0.80, counter_test_status="unavailable"),
            _p("org/b", trust_score=0.79, counter_test_status="confirmed"),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    assert s.decision == "user-pick"
    assert "top-2 gap" in s.decision_reason
    assert "counter-test" in s.decision_reason


def test_threshold_matches_prophet_mesh() -> None:
    """Pinned in both repos. Two services that both believe they gate at the same threshold,
    gating differently, is exactly the drift the shared-vector discipline exists to catch."""
    assert AUTO_ROUTE_GAP_THRESHOLD == 0.15


# ── emitted shape conforms to the prophet-mesh schema ──────────────────────────

def test_emitted_json_matches_the_SolutionShortlist_shape() -> None:
    s = build_shortlist(
        [
            _p("org/strong", trust_score=0.95, catalog_verbs=("retrieve", "evaluate")),
            _p("org/weak", trust_score=0.50, catalog_verbs=("retrieve",)),
        ],
        abb="ABB.03", intent_verbs=["retrieve", "evaluate"],
        min_trust=0.45, access_grader=GRANT_ALL,
    )
    j = s.to_json(abb="ABB.03", mar_digest="sha256:" + "a" * 64, catalog_digest="sha256:" + "b" * 64)
    assert j["kind"] == "SolutionShortlist"
    assert j["abbRequirement"] == "ABB.03"
    assert j["autoRouteVerdict"]["decision"] == "auto-route"
    assert j["autoRouteVerdict"]["chosenIndex"] == 0
    assert j["derivedFrom"]["marDigest"].startswith("sha256:")
    for c in j["shortlist"]:
        assert c["matchReason"], "every candidate must carry a reason in the emitted shape"
        assert 0 <= c["score"] <= 1
        assert c["counterTestStatus"] in {"confirmed", "available", "unavailable"}
        assert c["accessDecision"]["grade"] in {"granted", "requires-consent", "denied"}


def test_empty_shortlist_emits_emptyReason_and_no_autoRouteVerdict() -> None:
    s = build_shortlist(
        [], abb="ABB.03", intent_verbs=["retrieve"], min_trust=0.45, access_grader=GRANT_ALL,
    )
    j = s.to_json(abb="ABB.03", mar_digest="sha256:" + "a" * 64, catalog_digest="sha256:" + "b" * 64)
    assert j["shortlist"] == []
    assert "emptyReason" in j
    assert "autoRouteVerdict" not in j, "an empty shortlist has no route to verdict on"


def test_canonical_json_keeps_non_ascii_raw() -> None:
    """Matches lawful-verdict and the TypeScript canonicaliser. The default would escape
    non-ASCII and every digest over accented content would diverge between languages."""
    assert canonical_json({"k": "café"}) == '{"k":"café"}'
    assert "\\u" not in canonical_json({"k": "中文 🔒"})


# ── the Eve Smith scenario, end to end ─────────────────────────────────────────

def test_eve_smith_cross_selling_scenario() -> None:
    """The exact flow from Zurich's E-RDA2 deck, run through our stack.

    Eve asks for a cross-selling report over the retail segment, including claims and billing
    data. Two participants claim ABB.03 (DATABASE). She has analyst but not billing-reader.

    What their Damian does: discovers the access gap mid-conversation and offers a prefilled
    link. What ours additionally does: refuses to auto-route BECAUSE of the gap, states the
    reason, and keeps the runner-up visible so Eve can choose the non-billing option instead
    of waiting on an approval she may not need.
    """
    def grader(repo: str):
        if repo == "org/billing-warehouse":
            return ("requires-consent", "Eve lacks billing-reader on LOCAL BILLING",
                    "https://consent.socioprophet.io/request?subject=eve.smith"
                    "&resource=local-billing&roles=billing-reader&exp=1800003600&sig=deadbeef")
        return ("granted", "market and product data are open to analyst", None)

    participants = [
        _p("org/billing-warehouse", trust_score=0.92,
           catalog_verbs=("retrieve", "evaluate", "transform")),
        _p("org/market-warehouse", trust_score=0.78,
           catalog_verbs=("retrieve", "evaluate")),
    ]

    s = build_shortlist(
        participants, abb="ABB.03",
        intent_verbs=["retrieve", "evaluate", "transform"],
        min_trust=0.45, access_grader=grader,
    )

    # Both are shown — the consent-gated one is not hidden.
    assert len(s.candidates) == 2
    top = s.candidates[0]
    assert top.repo == "org/billing-warehouse"
    assert top.access_grade == "requires-consent"
    assert top.remediation_url and "billing-reader" in top.remediation_url

    # But it does NOT auto-route, and the reason names the access gap specifically.
    assert s.decision == "user-pick"
    assert "requires-consent" in s.decision_reason

    # The runner-up is fully usable right now — Eve has a choice, not just a wait.
    runner_up = s.candidates[1]
    assert runner_up.repo == "org/market-warehouse"
    assert runner_up.access_grade == "granted"

    # And the emitted envelope carries everything a UI needs to render both options.
    j = s.to_json(abb="ABB.03", mar_digest="sha256:" + "c" * 64, catalog_digest="sha256:" + "d" * 64)
    assert j["autoRouteVerdict"]["decision"] == "user-pick"
    assert j["shortlist"][0]["accessDecision"]["remediation"]["expectedReturn"] == "ArtifactConsentRecord"
    assert j["shortlist"][1]["accessDecision"]["grade"] == "granted"
