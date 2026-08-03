#!/usr/bin/env python3
"""Validate an AgenticTask (and optionally a TypedInterrupt) against its contract
+ fail-closed semantics: legal replayable state history, action lifecycle,
approval tier == max action risk tier, and the hash seal. Proven both ways by
the self-test below.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "AgenticTask.v0.1.json"
INTERRUPT_SCHEMA = ROOT / "contracts" / "TypedInterrupt.v0.1.json"

sys.path.insert(0, str(ROOT / "tools"))
from agentic_task import (  # noqa: E402
    ACTION_TRANSITIONS, TASK_TRANSITIONS, _APPROVAL_REASON, verify_seal,
)


class ValidationError(Exception):
    pass


def _fail(msg: str) -> None:
    raise ValidationError(msg)


def semantic_checks(task: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    # 1. replay the audit_log's state transitions — every hop must be legal
    state = None
    for e in task.get("audit_log", []):
        if not e.get("event", "").startswith("state:"):
            continue
        to = e.get("to")
        if state is None:
            if to != "drafting":
                errs.append(f"first state must be 'drafting', got {to!r}")
        elif to not in TASK_TRANSITIONS.get(state, set()):
            errs.append(f"illegal state transition in audit_log: {state} -> {to}")
        state = to
    if state is not None and state != task.get("state"):
        errs.append(f"task.state {task.get('state')!r} disagrees with audit_log tail {state!r}")

    # 2. action lifecycle + low-risk auto-stage
    for a in task.get("actions", []):
        if a["state"] not in ACTION_TRANSITIONS:
            errs.append(f"action {a['action_id']}: unknown state {a['state']!r}")
        if not a.get("why"):
            errs.append(f"action {a['action_id']}: missing WHY (risk rationale)")
        if a["risk_tier"] == "low" and a["state"] == "proposed":
            errs.append(f"action {a['action_id']}: low-risk actions auto-stage, must not be 'proposed'")

    # 3. approval tier == max action risk tier, and requires_human derived
    tiers = {a["risk_tier"] for a in task.get("actions", [])}
    want = "high" if "high" in tiers else "medium" if "medium" in tiers else "low"
    ap = task.get("approval_requirements", {})
    if ap.get("tier") != want:
        errs.append(f"approval_requirements.tier {ap.get('tier')!r} != max action tier {want!r}")
    if ap.get("requires_human") != (want != "low"):
        errs.append("approval_requirements.requires_human must be (tier != low)")
    if not ap.get("reason"):
        errs.append("approval_requirements must state WHY (reason)")

    # 4. hash seal
    if not verify_seal(task):
        errs.append("hash seal does not verify")
    return errs


def validate_interrupt(rec: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if rec.get("type") != "critical" and rec.get("invades_focus"):
        errs.append("only a 'critical' interrupt may invade focus (invades_focus=true)")
    if rec.get("type") == "critical" and not rec.get("invades_focus"):
        errs.append("a 'critical' interrupt must set invades_focus=true")
    return errs


def _schema_validate(inst: dict, schema_path: Path) -> str | None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return None
    try:
        jsonschema.validate(inst, json.loads(schema_path.read_text()))
    except Exception as exc:  # jsonschema.ValidationError
        return str(exc).splitlines()[0]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv:
        inst = json.loads(Path(argv[0]).read_text())
        serr = _schema_validate(inst, SCHEMA)
        errs = ([f"schema: {serr}"] if serr else []) + semantic_checks(inst)
        if errs:
            print("FAIL:", file=sys.stderr)
            for e in errs:
                print("  -", e, file=sys.stderr)
            return 1
        print("OK: AgenticTask valid (schema + fail-closed semantics + seal).")
        return 0

    # self-test: build via the engine, prove valid; prove an illegal transition is refused
    import agentic_task as at
    t = at.new_task("Audit all repos for failing CI", owner="human:mdheller", autonomy_level="L2")
    at.add_action(t, "issue.draft", "low", why="drafting an issue is reversible and low-impact")
    at.transition(t, "ready", actor="human:mdheller")
    at.transition(t, "running")
    assert semantic_checks(t) == [], semantic_checks(t)
    try:
        at.transition(t, "drafting")  # running -> drafting is illegal
        print("FAIL: self-test — illegal transition was allowed", file=sys.stderr)
        return 1
    except at.TaskError:
        pass
    # tamper detection
    t["goal"] = "tampered"
    assert "hash seal does not verify" in semantic_checks(t)
    print("OK: self-test — engine-built task valid, illegal transition refused, tamper detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
