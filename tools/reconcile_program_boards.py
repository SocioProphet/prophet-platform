#!/usr/bin/env python3
"""Idempotent reconciler: converge GitHub Projects to board-spec.yaml.

For each board in the spec, ensure every declared issue is an item on the
GitHub Project (add if missing). Converge-not-recreate: adding an item that
already exists is a no-op, so re-running is safe. Setting per-item field
values (Status/Plane/...) is a follow-on pass; this MVP guarantees membership
parity, which is exactly what the fail-closed drill asserts.

Cutover portability: this is one adapter (GitHub). A Gitea adapter converging
the same spec is the sibling; the spec never changes.

Usage:
    python3 tools/reconcile_program_boards.py --spec <path> [--dry-run]
Auth: expects GH_TOKEN in the environment to be a MINTED token (GitHub App
installation token or WIF-derived) with Projects write — never a static PAT.
"""
from __future__ import annotations

import argparse
import sys

import board_spec_lib as lib

ISSUE_URL = "https://github.com/{repo}/issues/{n}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--owner", help="restrict to boards owned by this org "
                    "(a minted App token is single-org)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = lib.load_spec(args.spec)
    boards = lib.boards_with_items(spec)
    if args.owner:
        boards = [b for b in boards if b["owner_org"] == args.owner]

    added = present = failed = 0
    for b in boards:
        owner, number = b["owner_org"], b["github_number"]
        have = lib.project_issue_numbers(owner, number)
        for item in b["items"]:
            n = item["issue"]
            if n in have:
                present += 1
                continue
            url = ISSUE_URL.format(repo=item["repo"], n=n)
            if args.dry_run:
                print(f"  would add #{n} -> {b['title']} ({owner}#{number})")
                added += 1
                continue
            rc, _, err = lib.sh(
                ["gh", "project", "item-add", str(number), "--owner", owner, "--url", url]
            )
            if rc == 0:
                added += 1
                print(f"  added #{n} -> {b['title']}")
            else:
                failed += 1
                print(f"  FAILED #{n} -> {b['title']}: {err[:100]}")

    print(f"\nReconcile: present={present} added={added} failed={failed}"
          f"{' (dry-run)' if args.dry_run else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
