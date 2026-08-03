"""agentic_task — the AgenticTask object model + state machine.

The first-class task object for the agentic supervisory shell, with a fail-closed
lifecycle: only legal state transitions, an action lifecycle, risk-tier ->
approval derivation ("always state WHY"), and typed interrupts where only a
`critical` interrupt may invade operator focus. Every mutation re-seals the task
with a sha256 hash; `audit_log` entries can carry an AutonomyAdmissionReceipt
seal, so the task's decisions are backed by the estate's hash-sealed receipts.

Conforms to contracts/AgenticTask.v0.1.json, TypedInterrupt.v0.1.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

# ---- lifecycle (fail-closed transition tables) ------------------------------
TASK_TRANSITIONS: dict[str, set[str]] = {
    "drafting": {"ready", "aborted"},
    "ready": {"running", "aborted"},
    "running": {"waiting_for_evidence", "waiting_for_approval", "blocked", "completed", "aborted"},
    "waiting_for_evidence": {"running", "blocked", "aborted"},
    "waiting_for_approval": {"running", "blocked", "completed", "aborted"},
    "blocked": {"running", "aborted"},
    "completed": {"rolled_back"},
    "aborted": set(),
    "rolled_back": set(),
}
ACTION_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"staged", "failed"},
    "staged": {"approved", "failed", "reverted"},
    "approved": {"executing", "reverted"},
    "executing": {"succeeded", "failed"},
    "succeeded": {"reverted"},
    "failed": set(),
    "reverted": set(),
}
RISK_TIERS = ("low", "medium", "high")
INTERRUPT_TYPES = ("fyi", "review_requested", "blocked", "critical")
_LEVEL_RE = re.compile(r"^L[0-5]$")

_APPROVAL_REASON = {
    "low": "only low-risk actions (auto-stage, batch approval)",
    "medium": "a medium-risk action requires contextual review",
    "high": "a high-risk action requires explicit approval + richer evidence",
}


class TaskError(Exception):
    """Raised on an illegal transition or malformed input (fail-closed)."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _seal(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _reseal(task: dict[str, Any]) -> None:
    task.pop("hash", None)
    task["hash_algo"] = "sha256"
    task["hash"] = _seal({k: v for k, v in task.items() if k != "hash"})


# ---- factory + transitions --------------------------------------------------
def new_task(goal: str, owner: str, autonomy_level: str = "L1",
             scope: dict | None = None, policies: list[str] | None = None,
             budget: dict | None = None) -> dict[str, Any]:
    if not goal:
        raise TaskError("goal is required")
    if not _LEVEL_RE.match(autonomy_level):
        raise TaskError(f"autonomy_level must match L0-L5, got {autonomy_level!r}")
    now = _utc()
    task = {
        "version": "0.1",
        "task_id": f"urn:srcos:task:{uuid.uuid4().hex}",
        "goal": goal,
        "scope": scope or {},
        "policies": policies or [],
        "autonomy_level": autonomy_level,
        "budget": budget or {},
        "owner": owner,
        "state": "drafting",
        "created_at": now,
        "updated_at": now,
        "actions": [],
        "outputs": [],
        "audit_log": [{"at": now, "event": "state:drafting", "to": "drafting", "actor": owner}],
        "approval_requirements": {"tier": "low", "requires_human": False, "reason": _APPROVAL_REASON["low"]},
    }
    _reseal(task)
    return task


def transition(task: dict[str, Any], to_state: str, actor: str = "system",
               reason: str = "", receipt_ref: str | None = None) -> dict[str, Any]:
    frm = task["state"]
    if to_state not in TASK_TRANSITIONS.get(frm, set()):
        raise TaskError(f"illegal task transition {frm} -> {to_state}")
    task["state"] = to_state
    task["updated_at"] = _utc()
    entry: dict[str, Any] = {"at": task["updated_at"], "event": f"state:{to_state}",
                             "from": frm, "to": to_state, "actor": actor}
    if reason:
        entry["reason"] = reason
    if receipt_ref:
        entry["receipt_ref"] = receipt_ref
    task["audit_log"].append(entry)
    _reseal(task)
    return task


def add_action(task: dict[str, Any], capability: str, risk_tier: str, why: str,
               args: dict | None = None, evidence_refs: list[str] | None = None) -> dict[str, Any]:
    if risk_tier not in RISK_TIERS:
        raise TaskError(f"risk_tier must be one of {RISK_TIERS}")
    if not why:
        raise TaskError("every action must state WHY it fell into its risk tier")
    action = {
        "action_id": f"act:{uuid.uuid4().hex[:12]}",
        "capability": capability,
        "args": args or {},
        # low-risk actions auto-stage; medium/high stay proposed pending review
        "state": "staged" if risk_tier == "low" else "proposed",
        "risk_tier": risk_tier,
        "why": why,
        "evidence_refs": evidence_refs or [],
    }
    task["actions"].append(action)
    task["audit_log"].append({"at": _utc(), "event": f"action:{action['state']}",
                              "to": action["state"], "actor": "system", "reason": why})
    _derive_approval(task)
    task["updated_at"] = _utc()
    _reseal(task)
    return action


def transition_action(task: dict[str, Any], action_id: str, to_state: str,
                      actor: str = "system") -> dict[str, Any]:
    a = next((x for x in task["actions"] if x["action_id"] == action_id), None)
    if a is None:
        raise TaskError(f"no such action {action_id}")
    if to_state not in ACTION_TRANSITIONS.get(a["state"], set()):
        raise TaskError(f"illegal action transition {a['state']} -> {to_state}")
    frm = a["state"]
    a["state"] = to_state
    task["audit_log"].append({"at": _utc(), "event": f"action:{to_state}",
                              "from": frm, "to": to_state, "actor": actor})
    task["updated_at"] = _utc()
    _reseal(task)
    return a


def _derive_approval(task: dict[str, Any]) -> None:
    tiers = {a["risk_tier"] for a in task["actions"]}
    tier = "high" if "high" in tiers else "medium" if "medium" in tiers else "low"
    task["approval_requirements"] = {"tier": tier, "requires_human": tier != "low",
                                     "reason": _APPROVAL_REASON[tier]}


def make_interrupt(task: dict[str, Any], itype: str, message: str,
                   action_ref: str | None = None) -> dict[str, Any]:
    """Build a TypedInterrupt. `invades_focus` is true ONLY for `critical` — the
    rule is enforced here by construction, not left to the caller."""
    if itype not in INTERRUPT_TYPES:
        raise TaskError(f"interrupt type must be one of {INTERRUPT_TYPES}")
    if not message:
        raise TaskError("interrupt requires a message")
    return {
        "version": "0.1",
        "interrupt_id": f"int:{uuid.uuid4().hex[:12]}",
        "type": itype,
        "invades_focus": itype == "critical",
        "task_ref": task["task_id"],
        "action_ref": action_ref,
        "created_at": _utc(),
        "message": message,
        "requires_ack": itype in {"review_requested", "critical"},
    }


def verify_seal(task: dict[str, Any]) -> bool:
    return task.get("hash") == _seal({k: v for k, v in task.items() if k != "hash"})
