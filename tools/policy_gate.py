#!/usr/bin/env python3
"""Policy gate + PolicyDecision records (Workspace Control Plane, Phase 10 / D16, D17).

Emits a ``PolicyDecision`` record — verdict, policy_id, evidence refs, and
triggered rules — as a GUARDRAIL-kind OTel span whenever a named policy is
evaluated against the memory store.  The gate is fail-closed: an exception
during evaluation yields verdict ``blocked`` rather than silently allowing.

Design decisions:
  D16 — Policy decisions are full provenance records.  Every verdict carries
         the policy_id, the set of evidence claim_ids that triggered or cleared
         each rule, and the evaluation timestamp.  Audit trail is in the span
         tree: the GUARDRAIL span wraps the memory recall spans that produced
         the evidence.
  D17 — Gate composition: policies are lists of named rules each with a
         ``require`` (min count of evidence claims matching a term) and an
         optional ``forbid`` (any match blocks).  Combined verdict: ``allowed``
         only when all require rules pass AND no forbid rules fire.

Schema (policy_decision.v0):
  {
    "decision_id":   str,            # uuid
    "policy_id":     str,
    "verdict":       "allowed" | "blocked" | "error",
    "evaluated_at":  ISO-8601,
    "rules":         list[RuleResult],
    "evidence_refs": list[str],      # claim_ids used
    "error":         str | null,
  }

RuleResult:
  {
    "rule_name":   str,
    "passed":      bool,
    "match_count": int,
    "evidence":    list[str],        # claim_ids that matched
  }
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from otel_tracer import (  # type: ignore
    InMemoryExporter,
    Span,
    Tracer,
    OPENINFERENCE_SPAN_KIND,
    SPAN_KIND_GUARDRAIL,
    SPAN_KIND_RETRIEVER,
    MEMORY_TIER,
    MEMORY_TERM,
    MEMORY_RESULT_COUNT,
)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


# ── Rule and Policy definitions ───────────────────────────────────────────────

@dataclass
class Rule:
    """A single gate rule.

    Args:
        name: human-readable rule label (used in evidence + reporting)
        require_term: recall claims from the memory store matching this term
        min_count: minimum number of matching claims required to pass
        forbid_term: if set, ANY match on this term blocks the rule
    """
    name: str
    require_term: str
    min_count: int = 1
    forbid_term: Optional[str] = None


@dataclass
class Policy:
    """A named, ordered set of rules."""
    policy_id: str
    rules: list[Rule] = field(default_factory=list)
    description: str = ""


# ── PolicyDecision record ─────────────────────────────────────────────────────

def _rule_result(name: str, passed: bool, match_count: int,
                 evidence: list[str]) -> dict:
    return {
        "rule_name":   name,
        "passed":      passed,
        "match_count": match_count,
        "evidence":    list(evidence),
    }


def _decision(policy_id: str, verdict: str, rules: list[dict],
              evidence_refs: list[str], error: Optional[str] = None) -> dict:
    return {
        "decision_id":   f"pd-{uuid.uuid4().hex[:12]}",
        "policy_id":     policy_id,
        "verdict":       verdict,
        "evaluated_at":  _now(),
        "rules":         list(rules),
        "evidence_refs": list(evidence_refs),
        "error":         error,
    }


# ── PolicyGate ────────────────────────────────────────────────────────────────

class PolicyGate:
    """Evaluate named policies against a MemoryStore; emit GUARDRAIL spans.

    Each evaluation opens a root GUARDRAIL span.  Memory recall calls for each
    rule are child spans (RETRIEVER kind) linked to that root — creating a full
    audit trace: gate fired → which rules → which claims were evidence.

    Fail-closed: any exception during evaluation produces verdict ``blocked``
    and surfaces the error in both the decision record and the span.
    """

    def __init__(self, store, tracer: Tracer) -> None:
        self._store = store
        self._tracer = tracer

    def evaluate(self, policy: Policy) -> dict:
        """Evaluate ``policy`` and return a ``policy_decision.v0`` dict.

        Opens a GUARDRAIL span for the whole evaluation.  Rule-level recall is
        done with child spans so the trace shows which recall drove each verdict.
        """
        root_attrs = {
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_GUARDRAIL,
            "policy.policy_id":     policy.policy_id,
            "policy.rule_count":    len(policy.rules),
        }
        with self._tracer.span(f"policy.evaluate.{policy.policy_id}",
                               attributes=root_attrs) as root_span:
            try:
                return self._run(policy, root_span)
            except Exception as exc:
                decision = _decision(policy.policy_id, "blocked", [], [],
                                     error=str(exc))
                root_span.set_attribute("policy.verdict", "blocked")
                root_span.add_event("policy.error", {"error": str(exc)})
                return decision

    def _run(self, policy: Policy, root_span: Span) -> dict:
        all_evidence: list[str] = []
        rule_results: list[dict] = []
        overall_passed = True

        for rule in policy.rules:
            # require branch
            require_span = self._tracer.start_span(
                f"policy.rule.{rule.name}.require",
                parent_span=root_span,
                attributes={
                    OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
                    MEMORY_TIER:  "T4",
                    MEMORY_TERM:  rule.require_term,
                    "policy.rule_name":    rule.name,
                    "policy.require_term": rule.require_term,
                    "policy.min_count":    rule.min_count,
                },
            )
            matches = self._store.recall_by_term(rule.require_term)
            match_ids = [c.get("claim_id", "") for c in matches]
            require_span.set_attribute(MEMORY_RESULT_COUNT, len(matches))
            require_span.finish(status="ok")
            all_evidence.extend(match_ids)

            rule_passed = len(matches) >= rule.min_count

            # forbid branch
            if rule.forbid_term and rule_passed:
                forbid_span = self._tracer.start_span(
                    f"policy.rule.{rule.name}.forbid",
                    parent_span=root_span,
                    attributes={
                        OPENINFERENCE_SPAN_KIND: SPAN_KIND_RETRIEVER,
                        MEMORY_TIER:  "T4",
                        MEMORY_TERM:  rule.forbid_term,
                        "policy.rule_name":    rule.name,
                        "policy.forbid_term":  rule.forbid_term,
                    },
                )
                forbid_matches = self._store.recall_by_term(rule.forbid_term)
                forbid_ids = [c.get("claim_id", "") for c in forbid_matches]
                forbid_span.set_attribute(MEMORY_RESULT_COUNT, len(forbid_matches))
                forbid_span.finish(status="ok")
                if forbid_matches:
                    rule_passed = False
                    all_evidence.extend(forbid_ids)

            rule_results.append(
                _rule_result(rule.name, rule_passed, len(matches), match_ids)
            )
            if not rule_passed:
                overall_passed = False

        verdict = "allowed" if overall_passed else "blocked"
        dedup_evidence = list(dict.fromkeys(all_evidence))
        root_span.set_attribute("policy.verdict", verdict)
        root_span.set_attribute("policy.evidence_count", len(dedup_evidence))
        root_span.add_event(
            "policy.decided",
            {"verdict": verdict, "rule_count": len(rule_results)},
        )
        return _decision(policy.policy_id, verdict, rule_results, dedup_evidence)
