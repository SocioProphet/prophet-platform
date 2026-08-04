"""Prove INV-DEP-16 (the boot-memory-invariance gate) both ways, offline.

A gate that has only ever passed proves nothing. This drives the harness against two boot paths
over a REAL on-disk sqlite store (the same shape as compute-gateway's /data), across a 128x
record-count spread:

  * a SCALING hydrator that reads the whole store into RAM  => the gate FIRES (BootMemoryScales),
    the compute-gateway OOM anti-pattern the harness exists to catch;
  * a BOUNDED hydrator that reads only a COUNT              => the gate PASSES, delta within budget.

So the harness is shown to distinguish "memory scales with the store" from "memory is invariant to
it" — not merely to run green.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boot_memory_invariance import (  # noqa: E402
    BootMemoryScales,
    assert_boot_memory_invariant,
)

_RECORD_BODY = "x" * 4096  # ~4KB/record, so a whole-store load is unmistakably visible in RSS


def _seed(store: Path, n: int) -> None:
    """Write n records to an on-disk sqlite store (module-level so `spawn` can pickle it)."""
    conn = sqlite3.connect(store / "store.db")
    conn.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    conn.executemany("INSERT INTO records (id, body) VALUES (?, ?)",
                     [(i, _RECORD_BODY) for i in range(n)])
    conn.commit()
    conn.close()


# Retained at module scope in the child so the materialized store stays resident through the
# getrusage() sample — the anti-pattern, made concrete.
_HELD: object = None


def _boot_scaling(store: Path) -> None:
    """The OOM anti-pattern: hydrate the WHOLE store into memory at boot."""
    global _HELD
    conn = sqlite3.connect(store / "store.db")
    _HELD = [{"id": r[0], "body": r[1]} for r in conn.execute("SELECT id, body FROM records")]
    conn.close()


def _boot_bounded(store: Path) -> None:
    """The fix: read only what boot needs (a count/tip), never the whole store."""
    conn = sqlite3.connect(store / "store.db")
    conn.execute("SELECT COUNT(*) FROM records").fetchone()
    conn.close()


def test_scaling_hydrator_fails_the_gate():
    with pytest.raises(BootMemoryScales):
        assert_boot_memory_invariant(_seed, _boot_scaling, small_n=64, large_n=8192, budget_kb=8192)


def test_bounded_hydrator_passes():
    result = assert_boot_memory_invariant(_seed, _boot_bounded, small_n=64, large_n=8192, budget_kb=8192)
    assert result["delta_kb"] <= result["budget_kb"], result
