"""Teeth for the gate-registry meta-gate (never-fired == suspect).

The meta-gate must PASS the shipped registry (every registered gate has a teeth-test with a
negative case) and FAIL when a gate can't prove it fires — a teeth-test with no negative case, a
missing teeth-test, or a verify_*.py registered nowhere. A meta-gate that only ever passes would
be the very theater it exists to catch.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_gate_registry as chk  # noqa: E402


def test_shipped_registry_passes():
    import yaml
    obj = yaml.safe_load((chk.ROOT / "tools" / "gate_registry.yaml").read_text())
    assert chk.check(obj, chk.ROOT) == []


def test_negative_test_counter_recognizes_failure_cases():
    src = (
        "def test_resolves_ok(): ...\n"
        "def test_dangling_ref_fails(): ...\n"
        "def test_malformed_yaml_fails_closed(): ...\n"
    )
    assert chk.negative_test_count(src) == 2  # dangling_ref_fails, malformed_yaml_fails_closed


def test_gate_with_no_negative_case_is_flagged(tmp_path):
    # A pytest gate whose teeth-test has ONLY positive tests -> flagged.
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "tests").mkdir()
    (tmp_path / "tools" / "verify_thing.py").write_text("# a gate\n")
    (tmp_path / "tools" / "tests" / "test_verify_thing.py").write_text(
        "def test_happy_path(): assert True\n"  # no negative case
    )
    obj = {
        "gates": [{
            "id": "X", "kind": "pytest",
            "tool": "tools/verify_thing.py",
            "teeth_test": "tools/tests/test_verify_thing.py",
            "min_negative_tests": 1,
        }],
        "known_unproven": [],
    }
    problems = chk.check(obj, tmp_path)
    assert any("negative-case" in p for p in problems), problems


def test_unregistered_verify_tool_is_flagged(tmp_path):
    # A verify_*.py present but in neither gates nor known_unproven -> ratchet fails.
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_orphan.py").write_text("# unregistered gate\n")
    obj = {"gates": [], "known_unproven": []}
    problems = chk.check(obj, tmp_path)
    assert any("verify_orphan.py" in p and "neither registered" in p for p in problems), problems


def test_known_unproven_tool_satisfies_ratchet_but_must_exist(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_orphan.py").write_text("# gate\n")
    # booked as debt -> ratchet satisfied, no violation for verify_orphan
    ok = chk.check({"gates": [], "known_unproven": [{"tool": "tools/verify_orphan.py"}]}, tmp_path)
    assert not any("verify_orphan.py" in p for p in ok), ok
    # but a debt entry for a NON-existent tool is a stale entry -> flagged
    stale = chk.check({"gates": [], "known_unproven": [{"tool": "tools/verify_ghost.py"}]}, tmp_path)
    assert any("verify_ghost.py" in p and "stale" in p for p in stale), stale


def test_missing_teeth_test_is_flagged(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "verify_thing.py").write_text("# gate\n")
    obj = {"gates": [{
        "id": "X", "kind": "pytest",
        "tool": "tools/verify_thing.py",
        "teeth_test": "tools/tests/test_verify_thing.py",  # does not exist
        "min_negative_tests": 1,
    }], "known_unproven": []}
    problems = chk.check(obj, tmp_path)
    assert any("no proof it can fire" in p for p in problems), problems


def test_malformed_registry_fails_closed():
    assert chk.check("not a mapping", chk.ROOT)  # non-empty violations
