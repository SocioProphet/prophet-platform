from app.models import AcademyRecordHeader, AcademyVisibility, LearningSearchRecord
from app.policy import AcademyPolicyContext, LocalVisibilityPolicyEvaluator


def record(visibility: AcademyVisibility | None = None) -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(
            object_id="lsr_policy_0001",
            object_type="LearningSearchRecord",
            policy_tags=["learning-loop", "search"],
        ),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why next learning action was recommended",
        text="Policy gated explanation.",
        target_ref="llr_policy_0001",
        evidence_ref_ids=["evidence://academy/span/0001"],
        governance_ref_ids=["policy-fabric://decision/example-0001"],
        visibility=visibility,
    )


def test_local_policy_allows_unrestricted_record() -> None:
    decision = LocalVisibilityPolicyEvaluator().decide(record(), AcademyPolicyContext(actor_id="user-1"))
    assert decision.allowed
    assert decision.decision is not None
    assert decision.decision["decision"] == "allow"
    assert decision.decision["action_ref"] == "action://academy/search/read"
    assert decision.decision_ref == "policy-fabric://decision/academy_visibility_decision::lsr_policy_0001"


def test_local_policy_denies_wrong_actor() -> None:
    visibility = AcademyVisibility(allowed_actor_ids=["allowed-user"])
    decision = LocalVisibilityPolicyEvaluator().decide(record(visibility), AcademyPolicyContext(actor_id="other-user"))
    assert not decision.allowed
    assert decision.decision is not None
    assert decision.decision["decision"] == "deny"
    assert decision.reason == "actor not allowed"


def test_local_policy_emits_request_shape() -> None:
    visibility = AcademyVisibility(allowed_actor_ids=["allowed-user"])
    decision = LocalVisibilityPolicyEvaluator().decide(record(visibility), AcademyPolicyContext(actor_id="allowed-user"))
    assert decision.request is not None
    assert decision.request["action"] == "academy.search.read"
    assert decision.request["resource"]["source"] == "ALEXANDRIAN_ACADEMY"
    assert decision.request["resource"]["entity_type"] == "LEARNING_ACTION_EXPLANATION"


def test_local_policy_allows_matching_workspace_and_jurisdiction() -> None:
    visibility = AcademyVisibility(
        allowed_actor_ids=["allowed-user"],
        allowed_workspace_ids=["academy-workspace"],
        allowed_jurisdiction_ids=["pa-us"],
    )
    decision = LocalVisibilityPolicyEvaluator().decide(
        record(visibility),
        AcademyPolicyContext(actor_id="allowed-user", workspace_id="academy-workspace", jurisdiction_id="pa-us"),
    )
    assert decision.allowed
    assert decision.decision is not None
    assert decision.decision["visibility_scope"]["workspace_id"] == "academy-workspace"
