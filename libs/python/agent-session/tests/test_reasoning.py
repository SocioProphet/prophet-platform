from __future__ import annotations

from agent_session.reasoning import Reasoning, RoutePolicy, lane_for


def test_light_lane_disallows_hosted() -> None:
    _, hosted, effort = lane_for(Reasoning.LIGHT, None)
    assert not hosted
    assert effort == "low"


def test_moderate_lane_disallows_hosted_by_default() -> None:
    _, hosted, effort = lane_for(Reasoning.MODERATE, None)
    assert not hosted
    assert effort == "medium"


def test_deep_lane_allows_hosted_by_default() -> None:
    _, hosted, effort = lane_for(Reasoning.DEEP, None)
    assert hosted
    assert effort == "high"


def test_sovereign_lane_never_allows_hosted() -> None:
    _, hosted, _ = lane_for(Reasoning.SOVEREIGN, None)
    assert not hosted


def test_local_only_policy_blocks_hosted_on_deep() -> None:
    _, hosted, _ = lane_for(Reasoning.DEEP, RoutePolicy.LOCAL_ONLY)
    assert not hosted


def test_hosted_ok_policy_enables_hosted_on_moderate() -> None:
    _, hosted, _ = lane_for(Reasoning.MODERATE, RoutePolicy.HOSTED_OK)
    assert hosted


def test_hosted_ok_policy_does_not_enable_hosted_on_light() -> None:
    _, hosted, _ = lane_for(Reasoning.LIGHT, RoutePolicy.HOSTED_OK)
    assert not hosted
