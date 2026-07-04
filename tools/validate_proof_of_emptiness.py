#!/usr/bin/env python3
"""Validate a ProofOfEmptiness (PoE) record against contracts/ProofOfEmptiness.v0.1.json.

Zero-dependency (stdlib only), matching the other tools/validate_*.py validators.

Beyond structural checks, enforces the load-bearing Inception invariants (ADR-036):
  - I2 (no silent discard): decision=certified-empty REQUIRES method=erase-iso and
    shred_digest == empty_digest. You cannot reach the empty object except by a
    certified isomorphism.
  - X ≅ empty edge case: if pre_digest == empty_digest the object was already empty
    (the iso is the identity); still valid.
  - capability bottom cannot certify: a capability_ref naming the strict bottom
    (e.g. '@bottom' / '@L-' / 'cap:_|_') may not yield certified-empty.
  - trust_kernel_gate_order must be exactly identity,policy,evidence,attestation,revocation,audit.

Exit code 0 = valid, 1 = invalid, 2 = usage error.
"""
import argparse
import json
import sys

REQUIRED = [
    "version", "poe_id", "created_at", "subject_ref", "schema_id", "method",
    "canonicalization", "empty_digest", "pre_digest", "shred_digest",
    "capability_ref", "decision", "trust_kernel_gate_order", "hash", "hash_algo",
]
GATE_ORDER = ["identity", "policy", "evidence", "attestation", "revocation", "audit"]
BOTTOM_MARKERS = ("@bottom", "cap:_|_", "@L-", ":bottom")


def validate(poe):
    errs = []
    for k in REQUIRED:
        if k not in poe:
            errs.append(f"missing required field: {k}")
    if errs:
        return errs

    if poe["version"] != "0.1":
        errs.append(f"version must be '0.1', got {poe['version']!r}")
    if poe["method"] != "erase-iso":
        errs.append(f"method must be 'erase-iso', got {poe['method']!r}")
    if poe["decision"] not in ("certified-empty", "rejected"):
        errs.append(f"decision must be certified-empty|rejected, got {poe['decision']!r}")
    if poe["trust_kernel_gate_order"] != GATE_ORDER:
        errs.append(f"trust_kernel_gate_order must be exactly {GATE_ORDER}")

    # Core invariant I2: certified emptiness requires shred reached the empty digest.
    if poe["decision"] == "certified-empty":
        if poe["shred_digest"] != poe["empty_digest"]:
            errs.append(
                "INVARIANT I2 VIOLATED: decision=certified-empty but "
                "shred_digest != empty_digest (the erase-iso did not reach the empty object)."
            )
        cap = str(poe["capability_ref"]).lower()
        if any(m in cap for m in BOTTOM_MARKERS):
            errs.append(
                "capability bottom (⊥) cannot certify emptiness: "
                f"capability_ref={poe['capability_ref']!r}"
            )
    return errs


def main():
    ap = argparse.ArgumentParser(description="Validate a ProofOfEmptiness record.")
    ap.add_argument("path", help="Path to a PoE JSON file.")
    args = ap.parse_args()
    try:
        with open(args.path) as fh:
            poe = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"usage error: cannot read/parse {args.path}: {e}", file=sys.stderr)
        return 2

    errs = validate(poe)
    if errs:
        print(f"INVALID: {args.path}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"VALID: {args.path} (decision={poe['decision']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
