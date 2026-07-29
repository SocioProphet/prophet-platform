#!/usr/bin/env python3
"""design-register gate — the register enforces itself (Metaphor→Mechanism C2).

Reads docs/design-register.yaml and:
  1. validates every entry's shape and status against the ladder;
  2. for every entry claiming status `wired` or above, REQUIRES a runnable
     `probe_cmd` and executes it — a failing probe fails this gate, so a design
     that rots (or a zero-caller library masquerading as a capability) turns the
     build red instead of waiting to be rediscovered by archaeology;
  3. prints the register as a status table, so every CI run answers "what did we
     design, and how much of it is real?" without anyone asking.

Exit 0 = every claim in the register is currently true. Anything else = the
register is lying, which is the one state this program exists to make impossible.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

LADDER = ["absent", "declared", "wired", "measured", "sealed"]
REQUIRED = {"id", "source", "mechanism", "owner", "status", "probe", "wave"}
ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs" / "design-register.yaml"
PROBE_TIMEOUT_S = 300


def fail(msg: str) -> None:
    print(f"::error::design-register: {msg}")
    sys.exit(1)


def main() -> None:
    doc = yaml.safe_load(REGISTER.read_text())
    entries = doc.get("register")
    if not isinstance(entries, list) or not entries:
        fail("register list missing or empty")

    seen: set[str] = set()
    failures: list[str] = []
    rows: list[tuple[str, str, str, str]] = []

    for e in entries:
        missing = REQUIRED - set(e)
        if missing:
            fail(f"entry {e.get('id', '<no id>')} missing fields: {sorted(missing)}")
        if e["id"] in seen:
            fail(f"duplicate id {e['id']}")
        seen.add(e["id"])
        if e["status"] not in LADDER:
            fail(f"{e['id']}: unknown status {e['status']!r} (ladder: {LADDER})")

        probe_result = "—"
        if LADDER.index(e["status"]) >= LADDER.index("wired"):
            cmd = e.get("probe_cmd")
            if not cmd:
                fail(f"{e['id']}: status {e['status']} requires a runnable probe_cmd "
                     f"(the ladder rule: no claim above its probe)")
            try:
                r = subprocess.run(cmd, shell=True, cwd=ROOT, timeout=PROBE_TIMEOUT_S,
                                   capture_output=True, text=True)
                probe_result = "PASS" if r.returncode == 0 else "FAIL"
                if r.returncode != 0:
                    failures.append(f"{e['id']}: probe failed (exit {r.returncode}): {cmd}\n"
                                    f"{(r.stdout + r.stderr)[-400:]}")
            except subprocess.TimeoutExpired:
                probe_result = "TIMEOUT"
                failures.append(f"{e['id']}: probe timed out after {PROBE_TIMEOUT_S}s: {cmd}")
        rows.append((e["id"], e["status"], str(e["wave"]), probe_result))

    width = max(len(r[0]) for r in rows) + 2
    print(f"\n{'DESIGN REGISTER':—^60}")
    for rid, status, wave, probe in rows:
        print(f"  {rid:<{width}} {status:<10} {wave:<12} probe={probe}")
    print("—" * 60)

    if failures:
        for f_ in failures:
            print(f"::error::{f_}")
        sys.exit(1)
    print("register truthful: every claim at or below its probe-verified status ✓")


if __name__ == "__main__":
    main()
