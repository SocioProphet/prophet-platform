"""Actuate the Prophet core catalog's declared invariants (SP-RETR-FIBER-001 §10.2 binding).

`prophet_core_catalog_seed.v1.json` *declares* five catalog invariants in prose. Prose is not a
control. This module makes them machine-checkable and fail-closed, and it is honest about the
cases it cannot decide.

**Ternary verdicts, deliberately the same algebra as the fiber-product verdict** (hg_fiber /
SP-RETR-FIBER-001 §3.3), because the situation is identical: an invariant is a constraint over
shared variables, and "the fields needed to test it are absent" is *not* a pass.

    PASS      the entry satisfies the invariant                     (a global section glues)
    VIOLATION the entry provably breaks it — always carries a witness (obstruction)
    ZERO      no test is possible: the predicate the invariant names has no field on the entry

Three of the five declared invariants name predicates the v1 seed has no field for —
`first-party`, `derivative-license attestation`, `commercial-use obligation gate`. Silently
passing those is how a declared control becomes an unenforced one, so instead:

**The gate: ZERO is tolerable for a candidate, never for an admitted source.**
`promotion_state == "admitted"` + any ZERO ⇒ BLOCKED. An undecidable obligation cannot ride
along into the admitted set; it must be made decidable by recording the field.

The optional fields that resolve a ZERO are `first_party`, `derivative_license_attestation`, and
`commercial_use_gate` — a reference/attestation id, never prose. `gadm` is the worked example:
its NC-academic commercial gate lives today only in `note`, which this gate refuses to accept.

stdlib only; runs in CI and offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PASS, VIOLATION, ZERO = "PASS", "VIOLATION", "ZERO"

# licenses whose reuse carries an obligation that a `public` wall_guard would leak past.
COPYLEFT_OR_RESTRICTED = ("cc-by-sa", "odbl", "cc-by-nc", "proprietary", "share-alike",
                          "noncommercial", "-nd-", "-nc-")
NONCOMMERCIAL = ("cc-by-nc", "noncommercial", "academic-noncommercial", "-nc-")
# a snapshot must be pinned to an immutable version; these refresh modes are unpinnable.
UNPINNED_REFRESH = ("live", "continuous", "streaming", "rolling", "none")


def _lic(entry: dict) -> str:
    return str(entry.get("license") or "").lower()


def _result(inv: str, entry: dict, verdict: str, witness: str) -> dict:
    return {"invariant": inv, "id": entry.get("id"), "verdict": verdict, "witness": witness,
            "promotion_state": entry.get("promotion_state")}


def inv1_snapshot_pinned(e: dict) -> dict:
    """snapshot_gcs => refresh MUST be release-pinned (immutable version hash)."""
    if e.get("cache_strategy") != "snapshot_gcs":
        return _result("INV-1", e, PASS, "not a snapshot")
    refresh = str(e.get("refresh") or "").lower()
    if refresh in UNPINNED_REFRESH:
        return _result("INV-1", e, VIOLATION, f"snapshot_gcs with unpinnable refresh={refresh!r}")
    return _result("INV-1", e, PASS, f"refresh={refresh!r}")


def inv2_obligation_not_public(e: dict) -> dict:
    """copyleft/NC/proprietary => wall_guard != public OR explicit derivative-license attestation."""
    if not any(k in _lic(e) for k in COPYLEFT_OR_RESTRICTED):
        return _result("INV-2", e, PASS, "unrestricted license")
    if e.get("wall_guard") != "public":
        return _result("INV-2", e, PASS, f"wall_guard={e.get('wall_guard')!r}")
    att = e.get("derivative_license_attestation")
    if att:
        return _result("INV-2", e, PASS, f"attestation={att}")
    # public + obligation-bearing license + no attestation FIELD: the invariant's own escape
    # hatch is unrecordable, so this is a no-test-possible, not a pass.
    return _result("INV-2", e, ZERO,
                   f"license={e.get('license')!r} is obligation-bearing and wall_guard=public, but "
                   "no `derivative_license_attestation` field exists to satisfy the exception")


def inv3_admitted_has_provenance(e: dict) -> dict:
    """promotion_state=admitted => upstream non-null OR first-party.

    `upstream` is derived-from (5/73 in the v1 seed), so a null upstream means a ROOT source —
    which is exactly the "first-party" case the invariant allows. But "first-party" has no field,
    so a null upstream is indistinguishable from an unrecorded provenance chain.
    """
    if e.get("promotion_state") != "admitted":
        return _result("INV-3", e, PASS, "not admitted")
    if e.get("upstream"):
        return _result("INV-3", e, PASS, f"upstream={e['upstream']}")
    if e.get("first_party") is True:
        return _result("INV-3", e, PASS, "declared first_party")
    if e.get("first_party") is False:
        return _result("INV-3", e, VIOLATION, "first_party=false and no upstream — provenance chain is broken")
    return _result("INV-3", e, ZERO,
                   "admitted with null upstream and no `first_party` field — root source and "
                   "unrecorded provenance are indistinguishable")


def inv4_restricted_needs_grant(e: dict) -> dict:
    """wall_guard=restricted blocks default egress; requires a WallGuardCatalogVisibility grant."""
    if e.get("wall_guard") != "restricted":
        return _result("INV-4", e, PASS, f"wall_guard={e.get('wall_guard')!r}")
    grant = e.get("wall_guard_grant")
    if grant:
        return _result("INV-4", e, PASS, f"grant={grant}")
    return _result("INV-4", e, ZERO,
                   "wall_guard=restricted but no `wall_guard_grant` reference — the required "
                   "WallGuardCatalogVisibility grant is not recorded")


def inv5_nc_needs_commercial_gate(e: dict) -> dict:
    """NC license => commercial-use obligation gate BEFORE any admitted promotion."""
    if not any(k in _lic(e) for k in NONCOMMERCIAL):
        return _result("INV-5", e, PASS, "not a non-commercial license")
    if e.get("promotion_state") != "admitted":
        return _result("INV-5", e, PASS, f"NC but promotion_state={e.get('promotion_state')!r}")
    gate = e.get("commercial_use_gate")
    if gate:
        return _result("INV-5", e, PASS, f"gate={gate}")
    return _result("INV-5", e, ZERO,
                   f"license={e.get('license')!r} is non-commercial and promotion_state=admitted, "
                   "but no `commercial_use_gate` reference exists (a prose note is not a gate)")


INVARIANTS = (inv1_snapshot_pinned, inv2_obligation_not_public, inv3_admitted_has_provenance,
              inv4_restricted_needs_grant, inv5_nc_needs_commercial_gate)


def evaluate(seed: dict) -> list[dict]:
    """Every (entry x invariant) verdict, in declaration order."""
    return [fn(e) for e in seed.get("entries", []) for fn in INVARIANTS]


def blocked(results: list[dict]) -> list[dict]:
    """The fail-closed gate: any VIOLATION, plus any ZERO on an ADMITTED entry.

    A ZERO on a candidate is a known gap to close. A ZERO on an admitted source is an obligation
    the estate has already taken on without being able to prove it is honoured — that is the
    thing that must never ship.
    """
    return [r for r in results
            if r["verdict"] == VIOLATION
            or (r["verdict"] == ZERO and r["promotion_state"] == "admitted")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="catalog_invariants",
                                 description="Fail-closed gate over the Prophet core catalog's declared invariants.")
    ap.add_argument("seed", nargs="?",
                    default=str(Path(__file__).resolve().parents[1]
                                / "contracts/crystal-atlas/catalog/prophet_core_catalog_seed.v1.json"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    seed = json.loads(Path(a.seed).read_text())
    results = evaluate(seed)
    bad = blocked(results)
    zeros = [r for r in results if r["verdict"] == ZERO]

    if a.json:
        print(json.dumps({"ok": not bad, "blocked": bad, "zero_count": len(zeros),
                          "total": len(results)}, indent=2))
    else:
        for r in bad:
            print(f"  ✗ [{r['invariant']}] {r['id']} ({r['promotion_state']}): {r['witness']}", file=sys.stderr)
        candidate_zeros = len(zeros) - len([r for r in bad if r["verdict"] == ZERO])
        print(f"catalog: {len(seed.get('entries', []))} entries x {len(INVARIANTS)} invariants; "
              f"{len(bad)} blocking, {candidate_zeros} undecidable on non-admitted entries", file=sys.stderr)
        if bad:
            print("BLOCKED — an admitted source cannot carry an obligation the catalog cannot test.",
                  file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
