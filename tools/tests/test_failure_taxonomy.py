#!/usr/bin/env python3
"""Tests for the L0/L1/L2 failure taxonomy (two firewalls per failure mode + regress fixpoint)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import failure_taxonomy as ft  # noqa: E402


def test_shipped_registry_is_complete_and_has_a_fixpoint():
    v = ft.validate_registry()
    assert v["ok"] is True and v["fixpoint_present"] is True and v["errors"] == []


def test_every_entry_carries_L0_L1_L2_and_two_firewalls():
    for e in ft.TAXONOMY:
        assert ft.validate_entry(e) == [], e["failure_mode_id"]
        assert e["firewall_1"] and e["firewall_2"] and e["L2_meta_meta_failure"]


def test_an_entry_missing_the_meta_meta_level_is_rejected():
    bad = {"failure_mode_id": "FM-X", "title": "t", "L0_failure": "a", "L1_meta_failure": "b",
           "firewall_1": "x", "firewall_2": "y", "second_derivative": "z"}  # no L2
    assert "missing L2_meta_meta_failure" in ft.validate_entry(bad)


def test_registry_without_a_fixpoint_is_unbounded_regress():
    no_fix = [{"failure_mode_id": "FM-A", "title": "t", "L0_failure": "a", "L1_meta_failure": "b",
               "L2_meta_meta_failure": "c", "firewall_1": "one", "firewall_2": "two",
               "second_derivative": "d"}]
    v = ft.validate_registry(no_fix)
    assert v["ok"] is False and v["fixpoint_present"] is False


def test_nix_to_guix_mode_names_both_firewalls():
    e = ft.get("FM-0001")
    assert e["firewall_1"] == "adr_dependency_graph"
    assert e["firewall_2"] == "adr_conformance_sentinel"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ok: {len(fns)} failure-taxonomy tests passed")
    sys.exit(0)
