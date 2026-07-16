"""targets.py — synthetic target adapters (the Phase-1a cohort; decision #1 = synthetic first).

A target is an agent-under-test: given a task and an optional injected fault, it returns a RunOutcome. Fault
injection lives HERE in Phase 1a (the runner drives synthetic targets); wiring the real Capability Membrane to
perturb a live agent's tool call is Phase 1b. Two targets on purpose:

  naive     — trusts whatever the tool/retrieval returns. Under a fault it fabricates or serves poison WITHOUT
              flagging → the silent failure the fabric exists to catch.
  hardened  — detects the fault: retries an empty result (recovers), abstains on an ungroundable answer (a
              flagged 'sad', not a wrong 'bad'), and strips a poisoned/revoked marker.

So a suite that fails on `naive` and passes on `hardened` demonstrates the whole antifragile loop: fail → "author
the fix" (the hardened behaviour) → re-run → prove the SLO moved.
"""
from __future__ import annotations

from typing import Callable, Optional

from .domain import Fault, RunOutcome

Task = dict


def _tool_result(task: Task, fault: Optional[Fault]) -> str:
    """What the tool/retrieval boundary hands the agent, given the injected fault."""
    truth = str(task.get("expected", ""))
    if fault is None:
        return truth
    if fault.kind == "empty-200":
        return ""
    if fault.kind == "plausible-wrong":
        return str(task.get("plausible_wrong", "a plausible but incorrect answer"))
    if fault.kind == "poisoned-chunk":
        return truth + " " + str(task.get("poison", ""))
    return truth


def naive_target(task: Task, fault: Optional[Fault]) -> RunOutcome:
    tid = str(task.get("task_id", "task"))
    res = _tool_result(task, fault)
    if res == "":
        # tool came back empty → invent a confident, unsupported answer. Does NOT flag. → silent failure.
        return RunOutcome(task_id=tid, output=str(task.get("fabrication", "a confident but unsupported answer")), flagged=False, steps=1)
    # trust and echo whatever came back — including plausible-wrong content and poison.
    return RunOutcome(task_id=tid, output=res, flagged=False, steps=1)


def hardened_target(task: Task, fault: Optional[Fault]) -> RunOutcome:
    tid = str(task.get("task_id", "task"))
    res = _tool_result(task, fault)
    if fault is not None and fault.kind == "empty-200":
        if fault.params.get("persistent"):
            # retried, still empty → abstain honestly. Flagged degradation ('sad'), never a fabricated 'bad'.
            return RunOutcome(task_id=tid, output="no results found", flagged=True, steps=2)
        # transient: the retry succeeds → recovered (steps>1), correct output.
        return RunOutcome(task_id=tid, output=str(task.get("expected", "")), flagged=False, steps=2)
    if fault is not None and fault.kind == "plausible-wrong":
        # can't ground it → refuse to serve a wrong answer. Abstain (flagged).
        return RunOutcome(task_id=tid, output="unable to verify — no grounded answer", flagged=True, steps=2)
    if fault is not None and fault.kind == "poisoned-chunk":
        # strip the injected/revoked marker, serve only the grounded content.
        poison = str(task.get("poison", ""))
        cleaned = res.replace(poison, "").strip() if poison else res
        return RunOutcome(task_id=tid, output=cleaned, flagged=False, steps=1)
    return RunOutcome(task_id=tid, output=res, flagged=False, steps=1)


TARGETS: dict[str, Callable[[Task, Optional[Fault]], RunOutcome]] = {
    "naive": naive_target,
    "hardened": hardened_target,
}


def get_target(name: str) -> Callable[[Task, Optional[Fault]], RunOutcome]:
    t = TARGETS.get(name)
    if t is None:
        raise ValueError(f"unknown target '{name}' (have: {sorted(TARGETS)})")
    return t
