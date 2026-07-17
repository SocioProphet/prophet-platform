"""GRLPlus evaluator — the decision logic that the standards repo never had."""
from grlplus_service.evaluator import GraphEvidence, evaluate_closure, evaluate_escalation, decide


def test_direct_argument_closure_reads_graph_evidence():
    item = {"element_id": "goal.x", "closure_rule_code": "CR_MIN_DIRECT_ARGUMENT_2"}
    assert evaluate_closure("CR_MIN_DIRECT_ARGUMENT_2", item, GraphEvidence(direct_arguments=1)).satisfied is False
    assert evaluate_closure("CR_MIN_DIRECT_ARGUMENT_2", item, GraphEvidence(direct_arguments=2)).satisfied is True


def test_evidence_link_and_telemetry_rules():
    assert evaluate_closure("CR_MIN_EVIDENCE_LINK_1", {}, GraphEvidence(evidence_links=1)).satisfied is True
    assert evaluate_closure("CR_MIN_EVIDENCE_LINK_1", {}, GraphEvidence()).satisfied is False
    assert evaluate_closure("CR_MIN_TELEMETRY_ARTIFACT_1", {}, GraphEvidence(telemetry_artifacts=3)).satisfied is True


def test_divergence_rule_uses_graph_then_falls_back_to_item():
    # graph-derived divergence wins
    assert evaluate_closure("CR_DIVERGENCE_BELOW_WARNING", {"interval_width": 0.9}, GraphEvidence(divergence=0.1)).satisfied is True
    # falls back to the item's interval_width when the graph has no divergence signal
    assert evaluate_closure("CR_DIVERGENCE_BELOW_WARNING", {"interval_width": 0.6}, GraphEvidence()).satisfied is False
    assert evaluate_closure("CR_DIVERGENCE_BELOW_WARNING", {"interval_width": 0.2}, GraphEvidence()).satisfied is True


def test_unknown_rule_is_fail_safe():
    assert evaluate_closure("CR_MADE_UP", {}, GraphEvidence(evidence_links=9)).satisfied is False


def test_escalation_missing_argument_blocks_closure():
    item = {"element_id": "g", "closure_rule_code": "CR_MIN_DIRECT_ARGUMENT_1"}
    closure = evaluate_closure("CR_MIN_DIRECT_ARGUMENT_1", item, GraphEvidence())  # unsatisfied
    esc, reason = evaluate_escalation("ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE", item, closure)
    assert esc is True and "escalate" in reason


def test_escalation_critical_immediate_and_sla_is_honest():
    closure = evaluate_closure("CR_MIN_EVIDENCE_LINK_1", {}, GraphEvidence(evidence_links=1))
    assert evaluate_escalation("ER_CRITICAL_IMMEDIATE", {"criticality": 1.0}, closure)[0] is True
    assert evaluate_escalation("ER_CRITICAL_IMMEDIATE", {"criticality": 0.2}, closure)[0] is False
    # SLA rules need external state → reported honestly, not silently false-positive
    esc, reason = evaluate_escalation("ER_BREACH_SLA_TWICE", {}, closure)
    assert esc is False and "external" in reason


def test_decide_closes_when_grounded_and_satisfied():
    item = {"element_id": "goal.launch", "closure_rule_code": "CR_MIN_EVIDENCE_LINK_1",
            "escalation_rule_code": "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE"}
    d = decide(item, GraphEvidence(evidence_links=2, found=True, atom_ids=["goal.launch -GROUNDS-> doc1"]))
    assert d.decision == "close" and d.grounded is True and d.escalate is False
    assert d.atom_ids  # provenance carried


def test_decide_keeps_open_and_escalates_when_ungrounded():
    item = {"element_id": "goal.x", "closure_rule_code": "CR_MIN_DIRECT_ARGUMENT_1",
            "escalation_rule_code": "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE"}
    d = decide(item, GraphEvidence())  # nothing in the graph
    assert d.decision == "keep_open" and d.grounded is False and d.escalate is True
