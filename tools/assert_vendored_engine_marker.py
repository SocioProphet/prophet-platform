#!/usr/bin/env python3
"""Assert a vendored engine tarball is really the release it claims to be.

The load-bearing step of the re-vendor discipline (vendor-freshness-plane.md § Re-vendor
discipline, step 2): a `version` field is NOT evidence. `package.json` says whatever it
says regardless of what the bundle contains — a previous release shipped a stale `dist`
with a fresh version string in exactly this way. The only evidence is a discriminating
marker INSIDE the packed dist.

This tool is the generic mechanism; the marker VALUES come from the caller (the
vendor-freshness register's `version_marker`, carried into the re-vendor EffectRequest),
so there is no second opinion of "what distinguishes this release."

Two things worth stating because both have already gone wrong:

* It searches the extracted bytes with Python string containment, NEVER grep. grep
  false-negatives on the bundled dist (it treats the minified single-line bundle as
  binary and silently skips it), which would turn this evidence check into a rubber
  stamp. Verified: grep reports zero `PROP_NS` in the real 0.4.45 bundle that plainly
  contains it.
* A substring is not a marker. `"prop:"` appears in BOTH 0.4.40 and 0.4.45; only the
  full assignment `PROP_NS = "prop:"` distinguishes them. Pass the whole discriminating
  token as --expect, and pass known-decoy substrings as --forbid to prove the point.

Usage:
  assert_vendored_engine_marker.py <tarball> --expect 'PROP_NS = "prop:"' [--forbid ...]
                                   [--member package/ts/dist/index.js]
Exit 0 and print a receipt on success; exit 1 with the reason on failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

DEFAULT_MEMBER = "package/ts/dist/index.js"


def read_member(tarball: Path, member: str) -> str:
    with tarfile.open(tarball, "r:gz") as tar:
        try:
            handle = tar.extractfile(member)
        except KeyError:
            handle = None
        if handle is None:
            raise SystemExit(f"ERR: {tarball.name} has no member {member!r} — cannot assert the dist")
        return handle.read().decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assert a discriminating marker inside a vendored engine tarball's packed dist.")
    ap.add_argument("tarball", type=Path)
    ap.add_argument("--expect", action="append", default=[], metavar="MARKER",
                    help="marker string that MUST be present in the packed dist (repeatable)")
    ap.add_argument("--forbid", action="append", default=[], metavar="MARKER",
                    help="marker string that must be ABSENT — e.g. a decoy substring (repeatable)")
    ap.add_argument("--member", default=DEFAULT_MEMBER, help=f"tarball member to inspect (default {DEFAULT_MEMBER})")
    args = ap.parse_args(argv)

    if not args.tarball.exists():
        print(f"ERR: tarball not found: {args.tarball}", file=sys.stderr)
        return 1
    if not args.expect:
        print("ERR: at least one --expect marker is required (a version field is not evidence)", file=sys.stderr)
        return 1

    dist = read_member(args.tarball, args.member)
    digest = hashlib.sha256(args.tarball.read_bytes()).hexdigest()

    missing = [m for m in args.expect if m not in dist]
    present_forbidden = [m for m in args.forbid if m in dist]

    problems = []
    if missing:
        problems.append(f"expected markers absent from {args.member}: {missing}")
    if present_forbidden:
        problems.append(f"forbidden markers present in {args.member}: {present_forbidden}")

    receipt = {
        "tool": "prophet-platform.assert_vendored_engine_marker.v1",
        "tarball": str(args.tarball),
        "tarball_digest": f"sha256:{digest}",
        "member": args.member,
        "expected_present": args.expect,
        "forbidden_absent": args.forbid,
        "passed": not problems,
        "problems": problems,
        "non_claims": [
            "Asserts the packed dist carries the discriminating marker; does NOT rebuild or run the engine.",
            "Marker values are supplied by the caller (the register's version_marker); this tool holds no opinion of what a release is.",
        ],
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if problems:
        for p in problems:
            print(f"ERR: {p}", file=sys.stderr)
        return 1
    print(f"OK: {args.tarball.name} dist carries {len(args.expect)} expected marker(s), {len(args.forbid)} decoy(s) absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
