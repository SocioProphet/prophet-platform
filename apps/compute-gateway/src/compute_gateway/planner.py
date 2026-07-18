"""The planner — the capability registry as an agent ACTION SPACE (layer 6).

Given a goal (a set of desired CAPABILITIES + an intent label), the planner
treats the registry as an action space: it selects the kinds that PROVIDE those
capabilities and composes them into a governed `workflow` plan — observed reads
first (fan-out), then derivations that depend on them (fan-in). Compute becomes
something an agent can PLAN over, not just invoke.

The plan is a PREVIEW; it is never executed here. The client hands the returned
workflow spec to /v1/compute to run it under full governance (entitlement +
zero-trust grant + signed receipts). Planning is free — you may plan before you
pay; only execution is gated. That separation IS the governance property.

This ships a DETERMINISTIC capability planner (`strategy=capability-dag`, no
model in the request path — testable, explainable). It is a pluggable seam: an
LLM / noetica-mcp reasoner can register another strategy that emits the SAME
workflow-plan shape, so the surface and the governance never change.
"""
from __future__ import annotations

from typing import Any

from . import registry

# a kind's spec skeleton — a plan is a scaffold; the human/agent fills the payloads.
_SPEC_SKELETON: dict[str, dict[str, Any]] = {
    "graph-stats": {},
    "graph-query": {"label": ""},
    "notebook": {"code": ""},
    "spark": {"sql": ""},
    "inference": {"task": "embed", "input": []},
}

_LADDER = ["unknown", "hypothesis", "simulated", "observed", "derived", "verified", "attested"]


def _weakest(warrants: list[str]) -> str:
    if not warrants:
        return "unknown"
    return min(warrants, key=lambda w: _LADDER.index(w) if w in _LADDER else 0)


def plan(*, capabilities: list[str], project: str, intent: str | None,
         entitlement: str | None) -> dict[str, Any]:
    """Compose a governed workflow plan that satisfies the desired capabilities.

    Reads (observed, no user code) are scheduled first as a fan-out; everything
    else depends on them (fan-in) — the natural gather-then-derive shape. Returns
    a runnable `workflow` spec plus a per-step preview (entitlement + warrant) and
    an honest account of what could NOT be satisfied.
    """
    chosen: list[tuple[str, str]] = []   # (kind, capability) preserving request order
    seen_kinds: set[str] = set()
    unmet_caps: list[str] = []
    for cap in capabilities:
        kinds = registry.kinds_providing(cap)
        if not kinds:
            unmet_caps.append(cap)
            continue
        kind = kinds[0]                  # live-first (registry.kinds_providing orders)
        if kind not in seen_kinds:
            seen_kinds.add(kind)
            chosen.append((kind, cap))

    # partition into reads (observed + no user code) and derivations
    reads = [(k, c) for k, c in chosen if registry.KINDS[k]["epistemic"] == "observed"
             and not registry.KINDS[k]["executes_user_code"]]
    derives = [(k, c) for k, c in chosen if (k, c) not in reads]

    steps: list[dict] = []
    previews: list[dict] = []
    read_ids: list[str] = []
    for i, (kind, cap) in enumerate(reads):
        sid = f"read-{i+1}-{kind}"
        read_ids.append(sid)
        steps.append({"id": sid, "kind": kind, "spec": dict(_SPEC_SKELETON.get(kind, {}))})
        previews.append(_preview(sid, kind, cap, project, entitlement))
    for i, (kind, cap) in enumerate(derives):
        sid = f"derive-{i+1}-{kind}"
        # a derivation depends on every read (fan-in); if there are no reads it is a root
        steps.append({"id": sid, "kind": kind, "spec": dict(_SPEC_SKELETON.get(kind, {})),
                      **({"needs": list(read_ids)} if read_ids else {})})
        previews.append(_preview(sid, kind, cap, project, entitlement))

    unmet_ent = [p["id"] for p in previews if not p["entitled"]]
    warrant = _weakest([p["epistemic"] for p in previews])
    return {
        "strategy": "capability-dag",
        "intent": intent,
        "requested_capabilities": capabilities,
        "plan": {"kind": "workflow", "project": project, "spec": {"steps": steps}},
        "steps": previews,
        "warrant_preview": warrant,
        "unmet_capabilities": unmet_caps,
        "unmet_entitlements": unmet_ent,
        "runnable": not unmet_caps and not unmet_ent and bool(steps),
    }


def _preview(sid: str, kind: str, cap: str, project: str, entitlement: str | None) -> dict[str, Any]:
    d = registry.KINDS[kind]
    backend = d["default"]
    return {
        "id": sid, "kind": kind, "backend": backend, "satisfies": cap,
        "epistemic": d["epistemic"], "executes_user_code": d["executes_user_code"],
        "status": d["status"],
        "entitled": registry.entitled(project, kind, backend, entitlement),
    }
