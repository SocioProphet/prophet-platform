#!/usr/bin/env python3
"""ConsensusArbitrator — quorum arbitration over PolicyDecision records (Phase 12 / D20, D21).

Given a set of ``policy_decision.v0`` records (from ``PolicyGate.evaluate``),
applies a configurable quorum rule to produce a single ``ConsensusDecision``
record.  Emits the decision as a GUARDRAIL-kind OTel span with each input
PolicyDecision referenced as a child event.

Design decisions:
  D20 — Three quorum modes cover the space of useful arbitration:
          ``unanimous``  — all policies must be ``allowed``
          ``majority``   — strict majority (>50%) must be ``allowed``
          ``any``        — at least one ``allowed`` is sufficient
         An empty decision list yields verdict ``blocked``; there is no quorum
         over nothing.  Policies in ``error`` state count as ``blocked`` for the
         quorum calculation, preserving fail-closed behaviour.
  D21 — The ConsensusDecision record carries every input decision_id so the
         arbitration is fully auditable: the trace can reconstruct which
         PolicyDecisions were combined and which broke consensus.

Schema (consensus_decision.v0):
  {
    "consensus_id":     str,            # "cd-<hex12>"
    "quorum_mode":      "unanimous" | "majority" | "any",
    "verdict":          "allowed" | "blocked",
    "decided_at":       ISO-8601,
    "total":            int,            # number of decisions evaluated
    "allowed_count":    int,
    "blocked_count":    int,
    "input_decisions":  list[str],      # decision_ids in order evaluated
    "error":            str | null,
  }
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from otel_tracer import (  # type: ignore
    Tracer,
    OPENINFERENCE_SPAN_KIND,
    SPAN_KIND_GUARDRAIL,
)

QuorumMode = Literal["unanimous", "majority", "any"]


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _consensus_record(
    quorum_mode: QuorumMode,
    verdict: str,
    total: int,
    allowed_count: int,
    blocked_count: int,
    input_decisions: list[str],
    error: str | None = None,
) -> dict:
    return {
        "consensus_id":    f"cd-{uuid.uuid4().hex[:12]}",
        "quorum_mode":     quorum_mode,
        "verdict":         verdict,
        "decided_at":      _now(),
        "total":           total,
        "allowed_count":   allowed_count,
        "blocked_count":   blocked_count,
        "input_decisions": list(input_decisions),
        "error":           error,
    }


class ConsensusArbitrator:
    """Arbitrate over multiple PolicyDecision records using a quorum rule.

    Args:
        tracer:      OTel Tracer from ``otel_tracer`` (Phase 9).
        quorum_mode: ``"unanimous"`` | ``"majority"`` | ``"any"``

    Usage::

        arbitrator = ConsensusArbitrator(tracer, quorum_mode="majority")
        result = arbitrator.arbitrate([decision_a, decision_b, decision_c])
        # result is a consensus_decision.v0 dict

    Fail-closed: any exception → verdict ``blocked``, error surfaced in record
    and span.  Policies with verdict ``error`` count as ``blocked``.
    """

    def __init__(self, tracer: Tracer, quorum_mode: QuorumMode = "unanimous") -> None:
        self._tracer = tracer
        self._quorum_mode = quorum_mode

    @property
    def quorum_mode(self) -> QuorumMode:
        return self._quorum_mode

    def arbitrate(self, decisions: list[dict]) -> dict:
        """Arbitrate over a list of ``policy_decision.v0`` records.

        Opens a GUARDRAIL OTel span.  Each input decision is recorded as a
        span event for full audit trail.  Returns a ``consensus_decision.v0``
        dict.
        """
        span_attrs = {
            OPENINFERENCE_SPAN_KIND: SPAN_KIND_GUARDRAIL,
            "consensus.quorum_mode":   self._quorum_mode,
            "consensus.input_count":   len(decisions),
        }
        with self._tracer.span("consensus.arbitrate", attributes=span_attrs) as span:
            try:
                result = self._run(decisions, span)
            except Exception as exc:
                result = _consensus_record(
                    self._quorum_mode, "blocked", len(decisions), 0, len(decisions),
                    [d.get("decision_id", "") for d in decisions],
                    error=str(exc),
                )
                span.set_attribute("consensus.verdict", "blocked")
                span.add_event("consensus.error", {"error": str(exc)})
            return result

    def _run(self, decisions: list[dict], span) -> dict:
        input_ids = [d.get("decision_id", "") for d in decisions]
        total = len(decisions)

        # empty → blocked (D20: no quorum over nothing)
        if total == 0:
            span.set_attribute("consensus.verdict", "blocked")
            span.add_event("consensus.decided", {"verdict": "blocked", "reason": "empty"})
            return _consensus_record(
                self._quorum_mode, "blocked", 0, 0, 0, [],
            )

        allowed_count = sum(
            1 for d in decisions if d.get("verdict") == "allowed"
        )
        blocked_count = total - allowed_count

        # record each input as a span event
        for d in decisions:
            span.add_event(
                "consensus.input",
                {
                    "decision_id": d.get("decision_id", ""),
                    "policy_id":   d.get("policy_id", ""),
                    "verdict":     d.get("verdict", ""),
                },
            )

        verdict = self._apply_quorum(total, allowed_count)

        span.set_attribute("consensus.verdict", verdict)
        span.set_attribute("consensus.allowed_count", allowed_count)
        span.set_attribute("consensus.blocked_count", blocked_count)
        span.add_event(
            "consensus.decided",
            {"verdict": verdict, "allowed": allowed_count, "total": total},
        )

        return _consensus_record(
            self._quorum_mode, verdict, total, allowed_count, blocked_count, input_ids,
        )

    def _apply_quorum(self, total: int, allowed_count: int) -> str:
        if self._quorum_mode == "unanimous":
            return "allowed" if allowed_count == total else "blocked"
        if self._quorum_mode == "majority":
            return "allowed" if allowed_count > total / 2 else "blocked"
        if self._quorum_mode == "any":
            return "allowed" if allowed_count >= 1 else "blocked"
        raise ValueError(f"Unknown quorum_mode: {self._quorum_mode!r}")
