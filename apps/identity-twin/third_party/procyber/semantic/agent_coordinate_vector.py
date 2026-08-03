"""AgentCoordinateVector (S0) — the eleven axes, validated with teeth both ways.

Every agent declares itself on eleven named axes. The point is falsifiability:
a vector with ten or twelve coordinates is REJECTED structurally, not by
convention, and exactly one axis is the agent's `primary`. The three
middle-column axes name the two dual operators of the algebra and the meet that
reconciles them, so an agent that claims `tiferet` realised by anything other
than `meet` — or claims to *glue* on the restrictive axis — is caught here.

Pure stdlib, matching the kernel: this runs in the admission path and must not
take a round-trip. The JSON Schema in `contracts/AgentCoordinateVector.v0.1.json`
is the registry face; this module is the enforcement face, and it checks the two
cross-field rules JSON Schema cannot express cleanly (exactly-eleven,
exactly-one-primary) plus operator-axis coherence.
"""

from __future__ import annotations

import json
import sys
from typing import Dict, List

SCHEMA_VERSION = "v0.1"
KIND = "AgentCoordinateVector"

#: The eleven axes, in canonical order. Ten sefirot plus Da'at — the internal
#: model that ShELL Challenge 1 showed is the missing organ.
AXES: tuple = (
    "keter",     # charter / mandate — given, not computed
    "chochmah",  # hypothesis generation
    "binah",     # elaboration -> typed plan
    "daat",      # internal model + 5C/5G disposition balance
    "chesed",    # expansive operator = pushout
    "gevurah",   # restrictive operator = pullback
    "tiferet",   # the meet
    "netzach",   # continuity / durability
    "hod",       # measurement, when to stop
    "yesod",     # the single serialization channel
    "malchut",   # world-effect + receipt
)

#: The axes that MUST be realised by a specific library operator when they name
#: one. This is what stops the middle column being reimplemented ad hoc.
OPERATOR_AXES: Dict[str, str] = {
    "chesed": "pushout",
    "gevurah": "pullback",
    "tiferet": "meet",
}

ALLOWED_OPERATORS = frozenset({"pushout", "pullback", "meet", "none"})


def validate(doc: object) -> List[str]:
    """Return a list of human-readable errors. Empty list == valid.

    Never raises on shape: a malformed document is a validation failure to be
    reported, not an exception to be caught by the caller.
    """
    errors: List[str] = []

    if not isinstance(doc, dict):
        return [f"document must be an object, got {type(doc).__name__}"]

    if doc.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION!r}, got {doc.get('schemaVersion')!r}")
    if doc.get("kind") != KIND:
        errors.append(f"kind must be {KIND!r}, got {doc.get('kind')!r}")

    agent_id = doc.get("agentId")
    if not isinstance(agent_id, str) or not agent_id:
        errors.append("agentId must be a non-empty string")

    coords = doc.get("coordinates")
    if not isinstance(coords, dict):
        errors.append("coordinates must be an object")
        return errors

    # -- exactly eleven, by name: this is the "10 or 12 is rejected" rule ----- #
    present = set(coords)
    missing = [a for a in AXES if a not in present]
    extra = sorted(present - set(AXES))
    if missing:
        errors.append(f"missing coordinate axes: {missing}")
    if extra:
        errors.append(f"unknown coordinate axes (a vector is exactly the eleven): {extra}")

    # -- each axis well-formed; collect primaries; check operator coherence --- #
    primaries: List[str] = []
    for axis in AXES:
        cell = coords.get(axis)
        if cell is None:
            continue  # already reported as missing
        if not isinstance(cell, dict):
            errors.append(f"axis {axis!r} must be an object")
            continue
        primary = cell.get("primary")
        if not isinstance(primary, bool):
            errors.append(f"axis {axis!r} must declare boolean 'primary'")
        elif primary:
            primaries.append(axis)

        operator = cell.get("operator")
        if operator is not None:
            if operator not in ALLOWED_OPERATORS:
                errors.append(f"axis {axis!r} has unknown operator {operator!r}")
            elif axis in OPERATOR_AXES and operator not in ("none", OPERATOR_AXES[axis]):
                errors.append(
                    f"axis {axis!r} must be realised by {OPERATOR_AXES[axis]!r}, "
                    f"not {operator!r}"
                )
            elif axis not in OPERATOR_AXES and operator != "none":
                errors.append(
                    f"axis {axis!r} is not an operator axis but claims operator {operator!r}"
                )

    # -- exactly one primary: rejects zero and rejects two ------------------- #
    if len(primaries) == 0:
        errors.append("no primary axis declared; exactly one is required")
    elif len(primaries) > 1:
        errors.append(f"exactly one primary axis is required, got {len(primaries)}: {primaries}")

    return errors


def is_valid(doc: object) -> bool:
    return not validate(doc)


def _main(argv: List[str]) -> int:
    if not argv:
        print("usage: agent_coordinate_vector.py <vector.json> [...]", file=sys.stderr)
        return 2
    failed = 0
    for path in argv:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        errs = validate(doc)
        if errs:
            failed += 1
            print(f"FAIL {path}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {path}")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover - CLI glue
    raise SystemExit(_main(sys.argv[1:]))
