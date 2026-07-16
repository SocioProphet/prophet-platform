"""oracles.py — invariant oracles: the ground truth that decides whether an output is CORRECT.

Each oracle answers one question: did the invariant HOLD for this output? The engine combines a violated
invariant with "the run did not flag a problem" to compute the silent-failure — the metric infra chaos cannot see.

V0 invariants (resolved 2026-07-16): exactString + grounded + non-fabricated + revoked-not-served. The last two
reuse the estate's provenance-fidelity posture and the commons revocation guarantee.
"""
from __future__ import annotations

from typing import Callable

Task = dict  # {task_id, query, expected, abstain_markers?, revoked_marker?}


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def inv_exact_string(output: str, task: Task) -> bool:
    return output == task.get("expected")


def inv_grounded(output: str, task: Task) -> bool:
    """Holds if the expected (ground-truth) answer is present — the output is grounded in truth, not drifted."""
    expected = _norm(task.get("expected", ""))
    return bool(expected) and expected in _norm(output)


ABSTENTIONS = ("i don't know", "no results", "cannot answer", "insufficient", "no evidence", "unable to", "not found")


def _is_abstention(output: str) -> bool:
    o = _norm(output)
    return o == "" or any(a in o for a in ABSTENTIONS)


def inv_non_fabricated(output: str, task: Task) -> bool:
    """Holds if the output is EITHER correct OR an honest abstention — never a confident WRONG answer.

    This is the one that catches the classic failure: a tool returns empty, and the agent invents a plausible
    answer instead of saying "no results". Abstaining is fine (that's a 'sad', flagged degradation); fabricating
    a wrong answer is the 'bad' the oracle exists to catch.
    """
    if inv_grounded(output, task):
        return True
    return _is_abstention(output)


def inv_revoked_not_served(output: str, task: Task) -> bool:
    """Commons regression: the output must NOT contain content the author revoked (or a planted injection).

    The marker is the same string the retrieval fault injects — `revoked_marker` if the task names one, else the
    `poison` payload the poisoned-chunk fault plants (they are one and the same thing from the oracle's view).
    """
    marker = task.get("revoked_marker") or task.get("poison")
    if not marker:
        return True
    return _norm(marker) not in _norm(output)


ORACLES: dict[str, Callable[[str, Task], bool]] = {
    "exactString": inv_exact_string,
    "grounded": inv_grounded,
    "non-fabricated": inv_non_fabricated,
    "revoked-not-served": inv_revoked_not_served,
}


def invariant_holds(invariant: str, output: str, task: Task) -> bool:
    oracle = ORACLES.get(invariant)
    if oracle is None:
        raise ValueError(f"unknown invariant '{invariant}' (have: {sorted(ORACLES)})")
    return oracle(output, task)
