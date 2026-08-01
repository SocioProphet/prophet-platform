#!/usr/bin/env python3
"""Validate the DevSecOps Workroom against the shared-spec conformance profile.

Enforces (never-fired=suspect): a requirement marked `conforms`/`partial` whose
evidence pointer no longer holds is a FAILURE (catches silent drift). `bind`/
`scope-d` items are reported as pending (tracked, not yet failing). The checker
excludes itself and asserts against real files, so it cannot pass vacuously.

Exit 0 = no drift; exit 1 = a claimed-conformant requirement lost its evidence.
Usage: python3 tools/validate_workroom_spec_conformance.py [repo_root]
"""
import json, sys, pathlib

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
PROFILE = ROOT / "contracts/workroom/workroom-spec-conformance.v0.1.json"
SELF = pathlib.Path(__file__).resolve()


def main() -> int:
    if not PROFILE.exists():
        print(f"FAIL: profile missing: {PROFILE}")
        return 1
    prof = json.loads(PROFILE.read_text())
    reqs = prof.get("requirements", [])
    if not reqs:
        print("FAIL: profile declares zero requirements (vacuous)")
        return 1

    failures, pending, checked = [], [], 0
    for r in reqs:
        rid, status = r["id"], r.get("status")
        ev = r.get("evidence")
        # silent-pass guard: a conforms/partial requirement MUST carry evidence,
        # else drift (someone drops the evidence block) goes undetected.
        if status in ("conforms", "partial") and not ev:
            failures.append(f"{rid}: status '{status}' has no evidence block")
        if status in ("conforms", "partial") and ev:
            f = ROOT / ev["file"]
            # self-exclusion: a requirement may not cite the checker as its own evidence
            if f.resolve() == SELF:
                failures.append(f"{rid}: evidence points at the checker itself")
                continue
            needle = ev["must_contain"]
            if not f.exists():
                failures.append(f"{rid}: evidence file absent: {ev['file']}")
            elif needle not in f.read_text():
                failures.append(f"{rid}: evidence lost — '{needle}' not in {ev['file']}")
            else:
                checked += 1
        if status in ("bind", "partial", "scope-d"):
            pending.append(f"{rid} [{status}] {r['text']}")

    print(f"== workroom spec-conformance: {len(reqs)} requirements, {checked} evidence-checked ==")
    for p in pending:
        print(f"  PENDING  {p}")
    if failures:
        print("\nDRIFT / FAILURES:")
        for x in failures:
            print(f"  FAIL  {x}")
        return 1
    if checked == 0:
        print("FAIL: no requirement was evidence-checked (guard against vacuous pass)")
        return 1
    print(f"\nOK: no drift; {checked} conformance claims still backed by evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
