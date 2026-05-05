from __future__ import annotations

import pytest

from cell_service.policy import PolicyError, StaticPolicyEngine, require_allowed


def test_static_policy_default_allows_operation() -> None:
    engine = StaticPolicyEngine()
    decision = engine.decide("signal.ingest", {"policy_ref": "policy://source/demo"})
    assert decision["decision"] == "allow"
    assert decision["policy_ref"] == "policy://source/demo"
    assert decision["decided_at"].endswith("Z")


def test_static_policy_operation_override_to_review_required() -> None:
    engine = StaticPolicyEngine({"feed_item.emit": "review_required"})
    decision = engine.decide("feed_item.emit", {"policy_ref": "policy://feed/demo"})
    assert decision["decision"] == "review_required"
    assert decision["policy_ref"] == "policy://feed/demo"


def test_static_policy_rejects_unknown_decision_value() -> None:
    with pytest.raises(PolicyError, match="unsupported policy decision"):
        StaticPolicyEngine({"feed_item.emit": "unsupported"})


def test_require_allowed_requires_allow_decision() -> None:
    with pytest.raises(PolicyError, match="policy blocked feed_item.emit"):
        require_allowed({"decision": "review_required", "policy_ref": "policy://feed/demo"}, "feed_item.emit")


def test_policy_requires_operation_name() -> None:
    engine = StaticPolicyEngine()
    with pytest.raises(PolicyError, match="operation must be non-empty"):
        engine.decide("", {})
