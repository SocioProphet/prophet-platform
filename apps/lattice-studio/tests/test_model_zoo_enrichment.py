from lattice_studio.model_zoo import demo_model_zoo_entry
from lattice_studio.model_zoo_enrichment import (
    enrich_model_zoo_fixture,
    model_zoo_agentplane_tools,
    model_zoo_policy_gate,
)

EXPECTED_TOOL_NAMES = {"discover-model-zoo", "promote-model-zoo-entry", "evaluate-model-zoo-entry"}


def test_enrich_model_zoo_fixture_kind() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    assert result["kind"] == "ModelZooEnrichmentBundle"


def test_enrich_model_zoo_fixture_top_level_keys() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    assert "searchEnrichment" in result
    assert "agentplaneBindings" in result
    assert "policyFabricGate" in result
    assert "activeMetadataEvents" in result


def test_enrich_model_zoo_fixture_agentplane_bindings_count() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    assert len(result["agentplaneBindings"]) == 3


def test_enrich_model_zoo_fixture_agentplane_tool_names() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    tool_names = {t["name"] for t in result["agentplaneBindings"]}
    assert tool_names == EXPECTED_TOOL_NAMES


def test_enrich_model_zoo_fixture_agentplane_boundaries() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    for tool in result["agentplaneBindings"]:
        assert "no-authority-grant" in tool["boundary"]


def test_enrich_model_zoo_fixture_policy_gate_blocked() -> None:
    # demo entry has promotionGate.state == "needs-review" → gate must be blocked
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    assert result["policyFabricGate"]["blocked"] is True


def test_enrich_model_zoo_fixture_active_metadata_events_nonempty() -> None:
    result = enrich_model_zoo_fixture(demo_model_zoo_entry())

    assert len(result["activeMetadataEvents"]) > 0


def test_model_zoo_agentplane_tools_count() -> None:
    entry = demo_model_zoo_entry()["entry"]
    tools = model_zoo_agentplane_tools(entry)

    assert len(tools) == 3


def test_model_zoo_agentplane_tools_required_fields() -> None:
    entry = demo_model_zoo_entry()["entry"]

    for tool in model_zoo_agentplane_tools(entry):
        assert "toolId" in tool
        assert "inputSchema" in tool
        assert "outputSchema" in tool
        assert "policyRef" in tool


def test_model_zoo_agentplane_tools_names() -> None:
    entry = demo_model_zoo_entry()["entry"]
    names = {t["name"] for t in model_zoo_agentplane_tools(entry)}

    assert names == EXPECTED_TOOL_NAMES


def test_model_zoo_policy_gate_kind() -> None:
    entry = demo_model_zoo_entry()["entry"]
    gate = model_zoo_policy_gate(entry)

    assert gate["kind"] == "PromotionGateCheck"


def test_model_zoo_policy_gate_blocked_when_needs_review() -> None:
    entry = demo_model_zoo_entry()["entry"]
    # fixture has promotionGate.state == "needs-review"
    gate = model_zoo_policy_gate(entry)

    assert gate["blocked"] is True


def test_model_zoo_policy_gate_not_blocked_when_approved() -> None:
    entry = {**demo_model_zoo_entry()["entry"], "promotionGate": {"state": "approved"}}
    gate = model_zoo_policy_gate(entry)

    assert gate["blocked"] is False
