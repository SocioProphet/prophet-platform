"""Surface an impairment run into Noetica's task-result contract.

Noetica is the integration surface: it owns the chat surface, the steering UX and the
**governance-trail rendering**, per ``Noetica/docs/m3-superconscious-contract.md``. It
does NOT own policy admission, model routing, or evidence authority. This module
respects that boundary -- it renders a completed run into ``NoeticaTaskResult``
(``noetica.task.v0.1``, see ``Noetica/lib/types/task.ts``) so the trail can display it.
It does not claim any authority Noetica has delegated elsewhere.

One mapping decision is worth stating plainly, because the tempting version is a lie:

    policy_admitted = (a policy decision ref was actually supplied)

NOT ``True``. This rig runs on weights you already hold, so nothing needs to admit it
in order to execute -- but "admitted" in the governance trail means *a policy engine
admitted this*, and defaulting it to True would fabricate a governance fact that no
engine ever asserted. An un-admitted run is still perfectly valid local research; it
just should not render as though guardrail-fabric blessed it.

That matters more here than elsewhere: the superconscious interpretability schema
conditionally REQUIRES ``policy_decision_required: true`` for ``feature_steering``. A
run that steers discovered features and reports itself as admitted, with no decision
behind it, is exactly the over-claim the harness doctrine exists to prevent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..readout.metrics import DissociationVerdict, FacultyVector
from .superconscious import INTERVENTION_KIND_MAP

SCHEMA_VERSION = "noetica.task.v0.1"
POLICY_REF_LOCAL = "policy://interpretability/noetica-impair-local-white-box"


@dataclass
class TaskResultInputs:
    """Everything the envelope needs that the rig itself cannot know."""

    session_id: str
    request_hash: str
    policy_decision_ref: str | None = None      # from guardrail/policy fabric, if any
    tool_grant_refs: tuple[str, ...] = ()
    resolved_grant_refs: tuple[str, ...] = ()
    memory_scope_ref: str | None = None
    agentplane_run_id: str | None = None
    latency_ms: int = 0


def requires_policy_decision(intervention_kinds: list[str]) -> bool:
    """True when any op maps to ``feature_steering``, which v0 gates on a decision."""
    return any(
        INTERVENTION_KIND_MAP.get(k, (None, None))[0] == "feature_steering"
        for k in intervention_kinds
    )


def summarise(label: str, fv: FacultyVector, dose: float) -> str:
    gap = fv.fluency_competence_gap
    shape = (
        "competence fell while fluency held -- the intoxicant signature"
        if gap > 0.05 else
        "fluency and competence fell together -- a coarse lesion, not a dissociable impairment"
        if gap < -0.05 or (fv.fluency < 0.95 and abs(gap) <= 0.05) else
        "no material split between fluency and competence"
    )
    return (
        f"{label} @ dose {dose:g}: competence {fv.competence:.2f}, fluency "
        f"{fv.fluency:.2f} (gap {gap:+.2f}), working memory {fv.working_memory:.2f}, "
        f"consistency {fv.consistency:.2f}, calibration {fv.calibration:.2f} "
        f"-- all as a fraction of the paired sober control. {shape}."
    )


def task_result(
    *,
    run_record: Any,
    faculty: FacultyVector,
    label: str,
    model_id: str,
    inputs: TaskResultInputs,
    intervention_kinds: list[str] | None = None,
    verdict: DissociationVerdict | None = None,
    status: str = "success",
) -> dict[str, Any]:
    """Render one run as ``NoeticaTaskResult``.

    ``run_record`` is a ``provenance.log.RunRecord`` that has already been appended,
    so its receipt exists and can be referenced as the evidence anchor.
    """
    receipt = getattr(run_record, "receipt", None) or {}
    kinds = intervention_kinds or [
        i.get("kind", "") for i in getattr(run_record, "interventions", [])
    ]

    admitted = inputs.policy_decision_ref is not None
    content = summarise(label, faculty, getattr(run_record, "dose", 0.0))
    if verdict is not None:
        content += "\n\n" + verdict.report()
    if requires_policy_decision(kinds) and not admitted:
        content += (
            "\n\nNote: this run includes feature_steering, which the interpretability "
            "harness gates on a policy decision. No decision ref was supplied, so it is "
            "recorded as un-admitted evidence rather than admitted."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "run_id": getattr(run_record, "run_id", ""),
        "content": content,
        # Routing authority belongs to model-router; nothing was routed here. The rig
        # was pointed at one locally-held model, which is not the same thing.
        "model_routed": model_id,
        "provider": "noetica-impair-local-white-box",
        "model_overridden": False,
        "policy_admitted": admitted,
        "policy_ref": inputs.policy_decision_ref or POLICY_REF_LOCAL,
        "grant_refs": {
            "requested": list(inputs.tool_grant_refs),
            "resolved": list(inputs.resolved_grant_refs),
            "missing": [
                g for g in inputs.tool_grant_refs if g not in inputs.resolved_grant_refs
            ],
        },
        "memory_written": False,
        "memory_scope_ref": inputs.memory_scope_ref,
        "agentplane_run_id": inputs.agentplane_run_id,
        # The receipt IS the evidence anchor -- hash-chained and independently verifiable.
        "evidence_ref": receipt.get("id"),
        "replay_ref": getattr(run_record, "sober_ref_run_id", None),
        "request_hash": inputs.request_hash,
        "evidence_hash": receipt.get("outputs_sha"),
        "timestamp": _iso(getattr(run_record, "ts", None)),
        "latency_ms": inputs.latency_ms,
    }


def _iso(ts: float | None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts if ts else time.time()))
