#!/usr/bin/env python3
"""Fail-closed parity drill: does GitHub match board-spec.yaml?

For every board in the spec that declares issue items, assert each declared
issue is actually present on the corresponding GitHub Project. Any missing
item is DRIFT and the drill exits non-zero (fail-closed) — a scheduled run of
this on the default branch turns drift into a red CI signal that
github-ci-health-current watches. This is a control-that-cannot-fail: it is
proven to fire on seeded drift by tools/tests/test_board_parity_drill.py, so a
silent green is meaningful rather than merely "nothing checked".

Usage:
    python3 tools/board_parity_drill.py --spec <path-to-board-spec.yaml> [--json]
"""
from __future__ import annotations

import argparse
import json
import sys

import board_spec_lib as lib


def compute_drift(boards: list[dict], fetch) -> list[dict]:
    """Pure diff: boards = spec boards with items; fetch(owner, number) -> set of
    issue numbers present on that board. Returns a drift record per missing item.
    No network here so it is unit-testable both ways."""
    drift: list[dict] = []
    for b in boards:
        present = fetch(b["owner_org"], b["github_number"])
        for item in b.get("items", []):
            n = item["issue"]
            if n not in present:
                drift.append({
                    "board": b["title"],
                    "owner": b["owner_org"],
                    "project": b["github_number"],
                    "issue": n,
                    "kind": "missing_from_board",
                })
    return drift


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--owner", help="restrict to boards owned by this org "
                    "(a minted App token is single-org; MVP covers the App's org)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec = lib.load_spec(args.spec)
    boards = lib.boards_with_items(spec)
    if args.owner:
        boards = [b for b in boards if b["owner_org"] == args.owner]
    drift = compute_drift(boards, lib.project_issue_numbers)

    if args.json:
        print(json.dumps(drift, indent=2))
    else:
        checked = sum(len(b["items"]) for b in boards)
        print(f"Board parity drill: {len(boards)} boards, {checked} declared items checked.")
        if not drift:
            print("OK: every spec'd item is present on its GitHub Project.")
        else:
            print(f"DRIFT: {len(drift)} declared item(s) missing from their board:")
            for d in drift:
                print(f"  - {d['board']} (proj {d['owner']}#{d['project']}): issue #{d['issue']} missing")
            print("\nRun the reconciler (tools/reconcile_program_boards.py) to converge, "
                  "then investigate why the drift occurred.")

    return 1 if drift else 0  # fail-closed


if __name__ == "__main__":
    sys.exit(main())
