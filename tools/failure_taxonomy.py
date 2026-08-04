#!/usr/bin/env python3
"""Failure taxonomy — every failure mode carried to its meta and meta-meta level.

The operator's rule: for each failure mode, identify the meta-failure and the meta-meta-failure —
that is what yields the *two* firewalls (a "second-derivative" dynamic), not one.

  L0  failure           (position)          the object-level thing that went wrong
  L1  meta-failure      (first derivative)  the CONTROL that should have caught L0 was absent/failing
  L2  meta-meta-failure (second derivative) nothing ensures the L1 control EXISTS across the estate;
                                            the control-generation process itself is failing

Each L1 is answered by **Firewall #1** (a per-case control); each L2 by **Firewall #2** (the
control-of-controls that guarantees Firewall #1 exists everywhere and watches whether coverage is
*accelerating away* from decisions). The infinite regress (L3, L4, …) is capped by one fixpoint entry:
the control-of-controls must govern ITSELF (firewall_1 == firewall_2), so two firewalls suffice.
"""
from __future__ import annotations

REQUIRED = ("failure_mode_id", "title", "L0_failure", "L1_meta_failure",
            "L2_meta_meta_failure", "firewall_1", "firewall_2", "second_derivative")

TAXONOMY = [
    {
        "failure_mode_id": "FM-0001",
        "title": "A decision does not percolate (Nix→Guix)",
        "L0_failure": "a new FROM-toolchain artifact (a .nix) was authored inside a scope under an "
                      "active FROM→TO swap (Nix→Guix), re-growing the surface the ADR is retiring.",
        "L1_meta_failure": "the ADR produced prose + a parity checklist but NO machine-actionable "
                           "dependency graph and NO gate — so no control could catch L0. Declared, "
                           "never enforced.",
        "L2_meta_meta_failure": "nothing in the estate ensures that EVERY ADR builds its dependency "
                                "graph + waves; the control-generation step is optional, so its "
                                "absence is invisible.",
        "firewall_1": "adr_dependency_graph",       # per-ADR graph + Wave-1 prevent + Wave-2 heal
        "firewall_2": "adr_conformance_sentinel",   # ensures every ADR has firewall_1
        "second_derivative": "count of ADRs lacking firewall_1 over time — is it accelerating?",
    },
    {
        # the fixpoint: the control-of-controls must itself be governed, else the regress never ends.
        "failure_mode_id": "FM-0000",
        "title": "The control-of-controls is itself ungoverned (regress cap)",
        "L0_failure": "Firewall #2 could be absent, disabled, or exempt itself, and nothing notices.",
        "L1_meta_failure": "no check verifies Firewall #2 is present and enabled.",
        "L2_meta_meta_failure": "the check-of-the-check would recurse forever (L3, L4, …).",
        "firewall_1": "adr_conformance_sentinel",
        "firewall_2": "adr_conformance_sentinel",   # SELF-fixpoint: it governs itself → regress capped
        "second_derivative": "self-coverage is a fixpoint; two firewalls suffice by construction.",
    },
]


def validate_entry(entry: dict) -> list[str]:
    """A taxonomy entry is well-formed only if it carries L0, L1, L2 and BOTH firewalls."""
    missing = [k for k in REQUIRED if not entry.get(k)]
    return [f"missing {k}" for k in missing]


def validate_registry(entries: list = None) -> dict:
    """Fail-closed. Every entry must be complete, and at least one fixpoint entry (firewall_1 ==
    firewall_2) must exist — that is what caps the meta-meta-meta… regress at two firewalls."""
    entries = TAXONOMY if entries is None else entries
    errors = []
    for e in entries:
        for m in validate_entry(e):
            errors.append(f"{e.get('failure_mode_id', '?')}: {m}")
    fixpoint = any(e.get("firewall_1") and e.get("firewall_1") == e.get("firewall_2") for e in entries)
    if not fixpoint:
        errors.append("no fixpoint entry (firewall_1 == firewall_2): the regress is unbounded")
    return {"ok": not errors, "count": len(entries), "fixpoint_present": fixpoint, "errors": errors}


def get(failure_mode_id: str, entries: list = None) -> dict | None:
    for e in (TAXONOMY if entries is None else entries):
        if e.get("failure_mode_id") == failure_mode_id:
            return e
    return None


if __name__ == "__main__":
    import json
    v = validate_registry()
    print(json.dumps({"validate": v,
                      "modes": [{"id": e["failure_mode_id"], "L0": e["L0_failure"][:48] + "…",
                                 "fw1": e["firewall_1"], "fw2": e["firewall_2"]} for e in TAXONOMY]},
                     indent=2))
