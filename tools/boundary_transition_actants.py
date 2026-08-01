"""BoundaryTransition v0.2 — the nine actantial roles, validated.

The actantial frame (Tesnière's actants + case grammar) is a complete,
non-redundant frame for a governed action: who, to what, for whom, by what and
why, when, where, to what purpose, how. It is universal linguistics, not any
third party's IP, and it replaces the ad-hoc field sets of v0.1 with one closed
role inventory.

`skeleton()` returns the frame's STRUCTURE with the natural-language surface of
every role dropped. Structure travels; surface does not — that is the mechanism
for transmitting event shape to a counterparty while withholding the descriptor
(the linkability / de-identification lever).
"""

from __future__ import annotations

from typing import Dict, List, Optional

SCHEMA_VERSION = "v0.2"

#: The closed inventory, in canonical order. `root` and `initiator` are required.
ROLES: tuple = (
    "root",         # the process / predicate
    "initiator",    # actant-1 — who acts
    "interactant",  # actant-2 — what is acted upon
    "recipient",    # actant-3 — for or to whom
    "cause",        # by what and why
    "time",         # when
    "place",        # where
    "intention",    # to what purpose
    "manner",       # how
)

REQUIRED_ROLES = ("root", "initiator")


def validate_actants(actants: object) -> List[str]:
    """Validate the actantial frame. Empty list == valid."""
    errors: List[str] = []
    if not isinstance(actants, dict):
        return [f"actants must be an object, got {type(actants).__name__}"]

    for role in REQUIRED_ROLES:
        value = actants.get(role)
        if not isinstance(value, str) or not value:
            errors.append(f"actant {role!r} is required and must be a non-empty string")

    extra = sorted(set(actants) - set(ROLES))
    if extra:
        errors.append(f"unknown actant role(s) (the inventory is closed): {extra}")

    for role, value in actants.items():
        if role in ROLES and role not in REQUIRED_ROLES:
            if value is not None and not isinstance(value, str):
                errors.append(f"actant {role!r} must be a string when present")

    return errors


def skeleton(actants: Dict[str, str]) -> Dict[str, bool]:
    """Which roles are populated, with all surface text dropped.

    A counterparty can see that a crossing had, say, a recipient and a purpose,
    and compute against that shape, without ever receiving who or what.
    """
    return {role: bool(actants.get(role)) for role in ROLES}


def validate_boundary_transition(doc: object) -> List[str]:
    """Validate the v0.2 envelope's actantial obligation.

    Scoped to what v0.2 ADDS over v0.1 (the actantial frame). The full v0.1
    envelope shape is validated by the JSON Schema in the contracts registry.
    """
    errors: List[str] = []
    if not isinstance(doc, dict):
        return [f"document must be an object, got {type(doc).__name__}"]
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION!r}, got {doc.get('schemaVersion')!r}")
    if "actants" not in doc:
        errors.append("v0.2 requires an 'actants' frame")
    else:
        errors.extend(validate_actants(doc["actants"]))
    return errors


def is_valid(doc: object) -> bool:
    return not validate_boundary_transition(doc)
