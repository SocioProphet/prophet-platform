"""Tests for the clean-room guard — both ways.

The guard must (a) pass on the actual framework files as shipped, (b) BITE on a real
leak, and (c) exclude itself. A guard only ever seen to pass is not a guard.
"""

from __future__ import annotations

from pathlib import Path

from tools.check_cleanroom import (
    FRAMEWORK_FILES,
    framework_files,
    scan_paths,
)


def test_the_shipped_framework_is_clean():
    # the real surface, as committed, must have no third-party marks
    assert scan_paths(framework_files()) == []


def test_the_guard_bites_on_a_real_leak(tmp_path: Path):
    leak = tmp_path / "leaky.py"
    # the exact class of leak the review caught: naming the third-party metalanguage
    leak.write_text("# derived from the IEML dictionary\nx = 1\n", encoding="utf-8")
    hits = scan_paths([str(leak)])
    assert len(hits) == 1
    assert hits[0][1] == 1  # line number
    assert hits[0][2].lower() == "ieml"


def test_the_guard_catches_each_forbidden_mark(tmp_path: Path):
    for token in ("IEML", "INTLEKT", "Lévy", "Levy"):
        f = tmp_path / f"{token}.md"
        f.write_text(f"see {token} for background\n", encoding="utf-8")
        assert scan_paths([str(f)]), f"{token} should have been flagged"


def test_the_guard_excludes_itself(tmp_path: Path):
    # even if the checker is explicitly passed to itself, it must not flag its own
    # forbidden-pattern source — a scanner that flags itself is broken.
    self_path = Path(__file__).resolve().parents[1] / "check_cleanroom.py"
    assert scan_paths([str(self_path)]) == []


def test_framework_manifest_excludes_the_guard_and_its_test():
    # self-exclusion by construction: the manifest must not list the guard/its test.
    assert not any("check_cleanroom" in rel for rel in FRAMEWORK_FILES)
