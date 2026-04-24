from app.models import AcademyRecordHeader, AcademyVisibility, LearningSearchRecord
from app.policy import AcademyPolicyContext, LocalVisibilityPolicyEvaluator


def record(visibility: AcademyVisibility | None = None) -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id="lsr_policy_0001", object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why next learning action was recommended",
        text="Policy gated explanation.",
        target_ref="llr_policy_0001",
        visibility=visibility,
    )


def test_local_policy_allows_unrestricted_record() -> None:
    decision = LocalVisibilityPolicyEvaluator().decide(record(), AcademyPolicyContext(actor_id="user-1"))
    assert decision.allowed
    assert decision.decision_ref == "policy-fabric://local-fallback/academy-search-visibility"


def test_local_policy_denies_wrong_actor() -> None:
    visibility = AcademyVisibility(allowed_actor_ids=["allowed-user"])
    decision = LocalVisibilityPolicyEvaluator().decide(record(visibility), AcademyPolicyContext(actor_id="other-user"))
    assert not decision.allowed


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
