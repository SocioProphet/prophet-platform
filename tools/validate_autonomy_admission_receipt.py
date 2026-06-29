#!/usr/bin/env python3
"""Validate AutonomyAdmissionReceipt v0.1.

Runtime receipt emitted when the platform admits/demotes/denies a choir role at
a requested autonomy level. The semantics mirror the canonical ladder in
SocioProphet/prophet-mesh (specs/ai-driven-development.yaml): the decision must
be internally consistent (granted vs requested vs decision), the trust-kernel
gate order is fixed, and a non-trivial granted level must cite evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED = {
    "version",
    "receipt_id",
    "created_at",
    "service_ref",
    "role",
    "requested_level",
    "granted_level",
    "decision",
    "gate",
    "evidence_required",
    "trust_kernel_gate_order",
    "subject_ref",
    "hash",
    "hash_algo",
}
DECISIONS = {"admit", "demote", "deny"}
TRUST_KERNEL_GATE_ORDER = ["identity", "policy", "evidence", "attestation", "revocation", "audit"]
LEVEL_RE = re.compile(r"^L[0-5]$")
NO_EVIDENCE = {"none", ""}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"{path}: expected JSON object")
    return payload


def _rank(level: str) -> int:
    return int(level[1:])


def validate_receipt(record: dict[str, Any]) -> None:
    missing = sorted(REQUIRED - set(record))
    if missing:
        fail("missing required fields: " + ", ".join(missing))

    if record["version"] != "0.1":
        fail("version must be '0.1'")
    for key in ("requested_level", "granted_level"):
        if not LEVEL_RE.match(str(record[key])):
            fail(f"{key} must match L0..L5")
    if "role_ceiling" in record and not LEVEL_RE.match(str(record["role_ceiling"])):
        fail("role_ceiling must match L0..L5")

    decision = record["decision"]
    if decision not in DECISIONS:
        fail(f"decision must be one of {sorted(DECISIONS)}")

    requested = _rank(record["requested_level"])
    granted = _rank(record["granted_level"])
    if granted > requested:
        fail("granted_level cannot exceed requested_level")
    if "role_ceiling" in record and granted > _rank(record["role_ceiling"]):
        fail("granted_level cannot exceed role_ceiling")

    # Decision must be consistent with the level delta (fail-closed semantics).
    if decision == "admit" and granted != requested:
        fail("decision 'admit' requires granted_level == requested_level")
    if decision == "demote" and not (0 < granted < requested):
        fail("decision 'demote' requires 0 < granted_level < requested_level")
    if decision == "deny" and granted != 0:
        fail("decision 'deny' requires granted_level == L0")

    if list(record["trust_kernel_gate_order"]) != TRUST_KERNEL_GATE_ORDER:
        fail("trust_kernel_gate_order must be " + " -> ".join(TRUST_KERNEL_GATE_ORDER))

    # A granted level above L0 carries a gate that needs evidence; cite it.
    if granted >= 1 and record["evidence_required"] not in NO_EVIDENCE:
        refs = record.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            fail("granted level above L0 requires non-empty evidence_refs")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_autonomy_admission_receipt.py <receipt.json>", file=sys.stderr)
        return 2
    try:
        validate_receipt(load_json(Path(argv[1])))
    except (ValidationError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {argv[1]} validates as AutonomyAdmissionReceipt v0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
