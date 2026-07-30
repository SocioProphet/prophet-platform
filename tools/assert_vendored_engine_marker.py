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

* It searches the extracted bytes with Python string containment, NEVER grep. The
  packed dist trips binary heuristics — 0.4.45's index.js is a 395 KB minified
  single-line bundle carrying a NUL byte at offset 5985 — and what a grep does when
  it decides a file is binary is not fixed: it varies across GNU/BSD builds, `-a`,
  locale, and any wrapper on PATH. In the dev shell this repo is usually driven
  from, `grep PROP_NS` on that bundle exits 1 while `/usr/bin/grep` finds all three
  occurrences.

  The point is not that grep is always wrong — it is that the answer depends on
  which grep ran, and an evidence check whose result depends on the searcher's
  binary-detection heuristic is not evidence. Python containment is deterministic
  over the bytes and has no such mode.

  (An earlier draft of this docstring asserted flatly that "grep reports zero
  PROP_NS in the real 0.4.45 bundle". That is false of /usr/bin/grep and was
  measured through the broken shell shim. Corrected here rather than deleted,
  because the wrong version was load-bearing justification.)
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


# A packed engine dist is a few hundred KB (0.4.45's index.js is 395 KB). 64 MiB
# is ~150x that — generous for any real release, and small enough that a
# decompression bomb cannot exhaust the runner. This matters because the tool is
# pointed at registry-pulled artifacts: the thing being inspected is exactly the
# thing not yet trusted, so it must not be read unbounded into memory.
MAX_MEMBER_BYTES = 64 * 1024 * 1024


def read_member(tarball: Path, member: str) -> str:
    with tarfile.open(tarball, "r:gz") as tar:
        try:
            info = tar.getmember(member)
        except KeyError:
            raise SystemExit(f"ERR: {tarball.name} has no member {member!r} — cannot assert the dist")
        # Only a regular file can carry a marker. A symlink/hardlink member would
        # make extractfile follow a link inside the archive, and a directory or
        # device yields None; refuse all of them by name rather than by accident.
        if not info.isfile():
            raise SystemExit(
                f"ERR: {tarball.name} member {member!r} is not a regular file "
                f"(type {info.type!r}) — refusing to treat it as the dist")
        if info.size > MAX_MEMBER_BYTES:
            raise SystemExit(
                f"ERR: {tarball.name} member {member!r} declares {info.size} bytes "
                f"> {MAX_MEMBER_BYTES} — refusing to read; this is not a packed dist")
        handle = tar.extractfile(info)
        if handle is None:
            raise SystemExit(f"ERR: {tarball.name} has no readable member {member!r} — cannot assert the dist")
        with handle:
            # Read one byte past the cap so a member whose declared size lies
            # about the compressed payload is still caught.
            raw = handle.read(MAX_MEMBER_BYTES + 1)
        if len(raw) > MAX_MEMBER_BYTES:
            raise SystemExit(
                f"ERR: {tarball.name} member {member!r} expands beyond {MAX_MEMBER_BYTES} bytes "
                "despite its declared size — refusing to read (decompression bomb)")
        # Python string containment, NEVER grep — see the module docstring. Verified
        # on the real 0.4.45 bundle: `grep PROP_NS` reports zero matches (the file is
        # classified as `data`) while `grep -a` reports three. grep here would make
        # this evidence check a rubber stamp.
        return raw.decode("utf-8", errors="replace")


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
