#!/usr/bin/env python3
"""Validate the Sovereign Retention Doctrine contract against its own invariants.

The doctrine is worthless if the file can drift out of the shape the enrolment
producer relies on, or -- worse -- if someone quietly relaxes an invariant
(residency off sovereign, vendor egress opted in by default, an auto class with
no delete ceiling). Those are precisely the changes that would look harmless in
review, so they are asserted here rather than trusted.

Exit 0 = the contract is well-formed AND every invariant holds. Exit 1 = it does
not, with the reason on stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts" / "governance" / "retention-policy.v0.json"


def errors(policy: dict) -> list[str]:
    errs: list[str] = []

    if not isinstance(policy, dict):
        return [f"policy must be a JSON object, got {type(policy).__name__}"]

    # Type-guard the containers before reaching into them. A validator whose job
    # is to fail safely must not crash with AttributeError when the JSON drifts
    # to the wrong shape: a traceback and a violation report are different
    # signals, and only one of them says what is actually wrong.
    inv = policy.get("universal_invariants", {})
    if not isinstance(inv, dict):
        errs.append(f"universal_invariants must be an object, got {type(inv).__name__}")
        inv = {}

    if inv.get("residency") != "sovereign":
        errs.append(f"residency must be 'sovereign', got {inv.get('residency')!r} "
                    f"-- governed bytes leaving our infra is not a tunable")
    if inv.get("vendor_opt_in") is not False:
        errs.append(f"vendor_opt_in must be false (opt-in, default-deny), got "
                    f"{inv.get('vendor_opt_in')!r}")

    classes = policy.get("classes", {})
    if not isinstance(classes, dict):
        errs.append(f"classes must be an object, got {type(classes).__name__}")
        classes = {}
    if not classes:
        errs.append("no classes defined")

    for name, c in classes.items():
        if not isinstance(c, dict):
            errs.append(f"class {name}: must be an object, got {type(c).__name__}")
            continue
        disp = c.get("disposition")
        if disp not in ("auto", "legal_hold"):
            errs.append(f"class {name}: disposition must be 'auto' or 'legal_hold', got {disp!r}")
            continue
        if disp == "auto":
            ttl, dele = c.get("ttl_days"), c.get("retention_delete_days")
            if not isinstance(dele, int) or dele <= 0:
                errs.append(f"class {name}: 'auto' disposition requires a finite positive "
                            f"retention_delete_days -- no retention forever by omission "
                            f"(got {dele!r})")
            if not isinstance(ttl, int) or ttl <= 0:
                errs.append(f"class {name}: 'auto' disposition requires a positive ttl_days (got {ttl!r})")
            elif isinstance(dele, int) and ttl > dele:
                errs.append(f"class {name}: ttl_days ({ttl}) must not exceed "
                            f"retention_delete_days ({dele}) -- a TTL past the hard-delete "
                            f"ceiling can never fire")
        else:  # legal_hold
            if c.get("retention_delete_days") is not None:
                errs.append(f"class {name}: legal_hold must NOT auto-delete "
                            f"(retention_delete_days must be null)")

    fallback = policy.get("fallback", {})
    if not isinstance(fallback, dict):
        errs.append(f"fallback must be an object, got {type(fallback).__name__}")
        fallback = {}
    fb = fallback.get("unknown_epistemic_status")
    if not isinstance(fb, str) or fb not in classes:
        errs.append(f"fallback class {fb!r} is not a defined class")
    elif classes.get(fb, {}).get("disposition") == "legal_hold":
        errs.append(f"fallback must be an auto class -- an unknown object defaulting to "
                    f"legal_hold could never be deleted; got {fb!r}")
    elif fb == "derived":
        errs.append("fallback must not be 'derived' -- an unknown object must not get the "
                    "SHORTEST retention. Doubt resolves toward keeping longer.")

    return errs


def main(path: Path = POLICY) -> int:
    if not path.exists():
        print(f"FAIL retention policy not found at {path}")
        return 1
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL retention policy is not valid JSON: {e}")
        return 1

    errs = errors(policy)
    for e in errs:
        print(f"FAIL {e}")
    if errs:
        print(f"\n{len(errs)} invariant violation(s)")
        return 1
    print(f"OK Sovereign Retention Doctrine v{policy.get('version')}: "
          f"{len(policy['classes'])} classes, invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
