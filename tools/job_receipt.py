#!/usr/bin/env python3
"""A one-line honesty convention for scheduled jobs: write a receipt when you finish.

The backup nightly exited 0 for days while every copy silently failed, because launchd only saw
the process's last `echo`, not whether the work happened. The fix generalizes: a job writes a
RECEIPT at completion — `{"job", "ts", "rc"}` — and something watches those receipts for
staleness (a job that stopped running) or a non-zero `rc` (a job that ran and failed). The
deploy-health alerter's `--receipts` mode already consumes exactly this shape, so adopting this
helper wires any job into that watch for free.

  # at the end of a Python job:
  from job_receipt import write_receipt
  write_receipt("nightly-backup", rc, directory="~/.local/state/receipts")

  # or from a shell job:
  job_receipt.py write nightly-backup "$rc" --dir ~/.local/state/receipts

`verify_receipts()` is the reader (a thin, importable form of the alerter's check) so a job can
also self-assert its peers are fresh.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def write_receipt(job: str, rc: int, *, directory: str | Path = "~/.local/state/receipts",
                  ts: float | None = None) -> Path:
    """Write ``{job, ts, rc}`` to ``<directory>/<job>.json``. Returns the path.

    Call it with the REAL exit code of the work — the whole point is that the receipt reflects
    what happened, not that the script reached its last line.
    """
    d = Path(directory).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{job}.json"
    path.write_text(json.dumps({"job": job, "ts": ts if ts is not None else time.time(),
                                "rc": int(rc)}) + "\n")
    return path


def verify_receipts(directory: str | Path, *, max_age_s: int, now: float | None = None,
                    expect: list[str] | None = None) -> list[str]:
    """Return a list of problems (empty = all fresh + rc 0). Mirrors the alerter's semantics.

    A missing expected receipt, a stale one, or a non-zero rc is a problem — the three ways a
    scheduled job silently lets you down.
    """
    d = Path(directory).expanduser()
    now = time.time() if now is None else now
    problems: list[str] = []
    found: dict[str, dict] = {}
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                data = json.loads(p.read_text())
                found[str(data.get("job") or p.stem)] = data
            except (json.JSONDecodeError, OSError):
                problems.append(f"{p.name}: unreadable receipt")
    for name in (expect or []):
        if name not in found:
            problems.append(f"{name}: missing (job wrote no receipt — did it run?)")
    for name, data in sorted(found.items()):
        ts = data.get("ts")
        if not isinstance(ts, (int, float)):
            problems.append(f"{name}: no/invalid ts")
        elif now - ts > max_age_s:
            problems.append(f"{name}: stale ({int(now - ts)}s > {max_age_s}s)")
        rc = data.get("rc")
        if rc is None:
            problems.append(f"{name}: no rc recorded")
        elif int(rc) != 0:
            problems.append(f"{name}: rc={rc}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write or verify job receipts.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="write a receipt")
    w.add_argument("job")
    w.add_argument("rc", type=int)
    w.add_argument("--dir", default="~/.local/state/receipts")
    v = sub.add_parser("verify", help="verify receipts are fresh + rc 0")
    v.add_argument("--dir", default="~/.local/state/receipts")
    v.add_argument("--max-age", type=int, default=93600, help="max age seconds (default 26h)")
    v.add_argument("--expect", action="append", default=[])
    args = ap.parse_args(argv)

    if args.cmd == "write":
        p = write_receipt(args.job, args.rc, directory=args.dir)
        print(f"wrote {p}")
        return 0
    problems = verify_receipts(args.dir, max_age_s=args.max_age, expect=args.expect)
    if problems:
        print(f"FAIL: {len(problems)} receipt problem(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    print("OK: all job receipts fresh and rc 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
