#!/usr/bin/env python3
"""Prove-it-fires for detect_unpushed_single_copy.py.

Teeth in both directions: the detector must FLAG a planted local-only commit
and CLEAR the moment it is pushed -- and a fully-pushed clean clone must read as
zero (the negative control that catches a detector which flags everything).

Run directly (named selftest_* so no pytest run collects it):

    python3 tools/selftest_detect_unpushed_single_copy.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DETECTOR = HERE / "detect_unpushed_single_copy.py"

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def g(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, env=ENV,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def detect(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DETECTOR), "--roots", str(root), "--max-depth", "2"],
        capture_output=True, text=True, env=ENV,
    )


def make_pushed_clone(base: Path, name: str) -> tuple[Path, Path]:
    """Return (remote_bare, working_clone) with one commit already pushed."""
    remote = base / f"{name}.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    work = base / name
    subprocess.run(["git", "clone", str(remote), str(work)], check=True, env=ENV,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (work / "a.txt").write_text("hello\n")
    g(work, "add", "-A")
    g(work, "commit", "-m", "base")
    g(work, "push", "-u", "origin", "main")
    return remote, work


def case_unpushed_then_push() -> bool:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        _, work = make_pushed_clone(base, "repoA")
        # Negative baseline: everything pushed and clean -> rc 0.
        cp0 = detect(base)
        baseline_clean = cp0.returncode == 0
        # KNOWN POSITIVE: plant a local-only commit.
        (work / "b.txt").write_text("local only\n")
        g(work, "add", "-A")
        g(work, "commit", "-m", "PLANTED local-only work")
        cp1 = detect(base)
        flagged = cp1.returncode == 1 and "unpushed commit" in cp1.stdout and "PLANTED" in cp1.stdout
        # CLEARS: push it.
        g(work, "push", "origin", "main")
        cp2 = detect(base)
        cleared = cp2.returncode == 0

        ok = baseline_clean and flagged and cleared
        print(f"[{'PASS' if ok else 'FAIL'}] unpushed-commit lifecycle: "
              f"baseline_clean={baseline_clean} flagged_when_local={flagged} cleared_when_pushed={cleared}")
        if not ok:
            for label, cp in (("baseline", cp0), ("planted", cp1), ("pushed", cp2)):
                print(f"---- {label} rc={cp.returncode} ----\n{cp.stdout}\n{cp.stderr}")
        return ok


def case_stash() -> bool:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        _, work = make_pushed_clone(base, "repoS")
        (work / "a.txt").write_text("dirty change\n")
        g(work, "stash", "push", "-m", "PLANTED stash")
        cp = detect(base)
        ok = cp.returncode == 1 and "stash" in cp.stdout and "PLANTED stash" in cp.stdout
        print(f"[{'PASS' if ok else 'FAIL'}] stash flagged: rc={cp.returncode}")
        if not ok:
            print(cp.stdout, cp.stderr)
        return ok


def case_no_remote() -> bool:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        repo = base / "orphan"
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (repo / "x.txt").write_text("never pushed anywhere\n")
        g(repo, "add", "-A")
        g(repo, "commit", "-m", "sole copy")
        cp = detect(base)
        ok = cp.returncode == 1 and "NO REMOTE" in cp.stdout
        print(f"[{'PASS' if ok else 'FAIL'}] no-remote repo flagged: rc={cp.returncode}")
        if not ok:
            print(cp.stdout, cp.stderr)
        return ok


def case_clean_negative_control() -> bool:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        make_pushed_clone(base, "clean1")
        make_pushed_clone(base, "clean2")
        cp = detect(base)
        ok = cp.returncode == 0
        print(f"[{'PASS' if ok else 'FAIL'}] clean pushed repos -> zero findings: rc={cp.returncode}")
        if not ok:
            print(cp.stdout, cp.stderr)
        return ok


def main() -> int:
    results = [
        case_unpushed_then_push(),
        case_stash(),
        case_no_remote(),
        case_clean_negative_control(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
