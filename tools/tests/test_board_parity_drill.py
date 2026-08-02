#!/usr/bin/env python3
"""Adversarial proof the board-parity drill fires both ways.

A drill that has never been shown to detect drift, and never been shown to
stay quiet on a matching estate, is as suspect as an unenforced rule
(control-that-cannot-fail). compute_drift is pure, so we drive it with a fake
`fetch` and assert: DRIFT on a board missing a declared item; SILENT when the
board contains every declared item.

Run: python3 tools/tests/test_board_parity_drill.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_parity_drill as drill  # noqa: E402

BOARDS = [
    {"title": "Product Surfaces", "owner_org": "SocioProphet", "github_number": 9,
     "items": [{"repo": "SocioProphet/socioprophet", "issue": 187},
               {"repo": "SocioProphet/socioprophet", "issue": 188}]},
    {"title": "Governance & Control Plane", "owner_org": "SocioProphet", "github_number": 7,
     "items": [{"repo": "SocioProphet/socioprophet", "issue": 490}]},
]


def test_fires_on_drift() -> None:
    # #188 is missing from Product Surfaces -> must be reported.
    def fetch(owner, number):
        return {187} if number == 9 else {490}
    drift = drill.compute_drift(BOARDS, fetch)
    assert len(drift) == 1, drift
    assert drift[0]["issue"] == 188 and drift[0]["board"] == "Product Surfaces"
    print("PASS: drill fires when a declared item is missing from its board")


def test_silent_when_in_parity() -> None:
    # every declared item present -> no drift.
    def fetch(owner, number):
        return {187, 188} if number == 9 else {490}
    drift = drill.compute_drift(BOARDS, fetch)
    assert drift == [], drift
    print("PASS: drill stays silent when GitHub matches the spec")


if __name__ == "__main__":
    test_fires_on_drift()
    test_silent_when_in_parity()
    print("\nBoth directions proven: the drill detects drift and stays quiet on parity.")
