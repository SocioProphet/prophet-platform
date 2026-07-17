"""GRLPlus policy evaluator — the missing engine.

The GRLPlus standards repo ships the *vocabulary* (closure_rule_catalog, escalation_rule_catalog)
and the export/validation shim, but never an evaluator: the exporter just copies whatever rule code
is already on an item. This module is the evaluator — it decides close / keep-open / escalate for a
semantic-worklist item by checking its closure rule against EVIDENCE gathered from the proof-carrying
knowledge graph (HellGraph). That makes GRLPlus real (it now actually decides) and integrates it with
the same graph the Graph-RL loop learns over: GRLPlus is the symbolic *shield* (which actions are
permissible / when to escalate), GRL is the learned optimizer inside it.

Pure + dependency-free so it is trivially testable; the graph fetch lives in server.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Divergence at/above this is "not below warning" (CR_DIVERGENCE_BELOW_WARNING fails). Interval width
# is the propagated-support uncertainty from GRL propagation (0 = tight/known, 1 = wide/unknown).
DIVERGENCE_WARNING = 0.5

CLOSURE_RULES = {
    "CR_MIN_DIRECT_ARGUMENT_1": "At least 1 direct argument must trace to the element.",
    "CR_MIN_DIRECT_ARGUMENT_2": "At least 2 direct arguments must trace to the element.",
    "CR_MIN_EVIDENCE_LINK_1": "At least 1 evidence link must support the element.",
    "CR_MIN_TELEMETRY_ARTIFACT_1": "At least 1 telemetry or control artifact must be attached.",
    "CR_DIVERGENCE_BELOW_WARNING": "Semantic divergence must fall below the configured warning threshold.",
    "CR_OWNER_APPROVAL_REQUIRED": "Named review owner must approve closure.",
}
ESCALATION_RULES = {
    "ER_BREACH_SLA_ONCE": "Escalate if SLA is breached once.",
    "ER_BREACH_SLA_TWICE": "Escalate if SLA is breached twice.",
    "ER_CRITICAL_IMMEDIATE": "Escalate immediately on critical severity.",
    "ER_PERSISTENT_HIGH_TWO_REVIEWS": "Escalate if high severity persists for two reviews.",
    "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE": "Do not allow closure when direct argument coverage is missing.",
}


@dataclass
class GraphEvidence:
    """What the knowledge graph knows about an element — counted from its incident edges."""
    direct_arguments: int = 0
    evidence_links: int = 0
    telemetry_artifacts: int = 0
    owner_approved: bool = False
    divergence: float | None = None  # graph-derived; falls back to the item's interval_width
    found: bool = False              # was the element node present in the graph at all?
    atom_ids: list[str] = field(default_factory=list)  # provenance: the edges/nodes consulted


@dataclass
class ClosureResult:
    rule: str
    satisfied: bool
    needed: str
    observed: str
    reason: str


@dataclass
class Decision:
    element_id: str
    closure: ClosureResult
    escalate: bool
    escalation_rule: str | None
    decision: str          # "close" | "keep_open"
    escalation_reason: str
    grounded: bool         # were the checks backed by a real graph node?
    atom_ids: list[str]


def evaluate_closure(rule: str, item: dict[str, Any], ev: GraphEvidence) -> ClosureResult:
    """Check one closure rule against the graph evidence. Fail-safe: unknown rule → not satisfied."""
    div = ev.divergence if ev.divergence is not None else item.get("interval_width")
    if rule == "CR_MIN_DIRECT_ARGUMENT_1":
        ok = ev.direct_arguments >= 1
        return ClosureResult(rule, ok, "≥1 direct argument", f"{ev.direct_arguments}", _cov(ok, "direct-argument"))
    if rule == "CR_MIN_DIRECT_ARGUMENT_2":
        ok = ev.direct_arguments >= 2
        return ClosureResult(rule, ok, "≥2 direct arguments", f"{ev.direct_arguments}", _cov(ok, "direct-argument"))
    if rule == "CR_MIN_EVIDENCE_LINK_1":
        ok = ev.evidence_links >= 1
        return ClosureResult(rule, ok, "≥1 evidence link", f"{ev.evidence_links}", _cov(ok, "evidence-link"))
    if rule == "CR_MIN_TELEMETRY_ARTIFACT_1":
        ok = ev.telemetry_artifacts >= 1
        return ClosureResult(rule, ok, "≥1 telemetry artifact", f"{ev.telemetry_artifacts}", _cov(ok, "telemetry"))
    if rule == "CR_DIVERGENCE_BELOW_WARNING":
        if div is None:
            return ClosureResult(rule, False, f"divergence < {DIVERGENCE_WARNING}", "unknown", "no divergence signal available")
        ok = div < DIVERGENCE_WARNING
        return ClosureResult(rule, ok, f"divergence < {DIVERGENCE_WARNING}", f"{div:.3f}",
                             "within tolerance" if ok else "divergence at/above warning threshold")
    if rule == "CR_OWNER_APPROVAL_REQUIRED":
        return ClosureResult(rule, ev.owner_approved, "owner approval", str(ev.owner_approved),
                             "approved" if ev.owner_approved else "awaiting owner approval")
    return ClosureResult(rule, False, "known closure rule", rule, f"unknown closure rule '{rule}' → keep open")


def _cov(ok: bool, kind: str) -> str:
    return f"{kind} coverage satisfied" if ok else f"{kind} coverage missing"


def evaluate_escalation(rule: str | None, item: dict[str, Any], closure: ClosureResult) -> tuple[bool, str]:
    """Decide escalation. SLA-time rules need external state and are reported as such (not silently false)."""
    crit = float(item.get("criticality", 0) or 0)
    if rule == "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE":
        if not closure.satisfied and closure.rule.startswith("CR_MIN_DIRECT_ARGUMENT"):
            return True, "direct-argument coverage missing blocks closure → escalate"
        return False, "direct-argument coverage present or not the gating rule"
    if rule == "ER_CRITICAL_IMMEDIATE":
        if crit >= 1.0:
            return True, "critical severity → immediate escalation"
        return False, "not critical severity"
    if rule in ("ER_BREACH_SLA_ONCE", "ER_BREACH_SLA_TWICE", "ER_PERSISTENT_HIGH_TWO_REVIEWS"):
        # These depend on SLA clocks / review history the evaluator does not hold; surface honestly.
        return False, f"{rule} needs external SLA/review state (not evaluated here)"
    return False, "no escalation rule"


def decide(item: dict[str, Any], ev: GraphEvidence) -> Decision:
    """Full decision for one worklist item: closure check + escalation, grounded in graph evidence."""
    closure_rule = item.get("closure_rule_code") or "CR_MIN_EVIDENCE_LINK_1"
    esc_rule = item.get("escalation_rule_code")
    closure = evaluate_closure(closure_rule, item, ev)
    escalate, esc_reason = evaluate_escalation(esc_rule, item, closure)
    return Decision(
        element_id=item.get("element_id", "?"),
        closure=closure,
        escalate=escalate,
        escalation_rule=esc_rule,
        decision="close" if closure.satisfied else "keep_open",
        escalation_reason=esc_reason,
        grounded=ev.found,
        atom_ids=ev.atom_ids,
    )
