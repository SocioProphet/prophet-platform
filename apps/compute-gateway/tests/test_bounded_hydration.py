"""Bounded/lazy boot hydration — the 2026-08-04 compute-gateway OOM, pinned two ways.

1. Boot-time resident memory does NOT scale with the receipt store (the OOM invariant), proven with
   the estate-wide boot-memory-invariance harness (tools/boot_memory_invariance.py, INV-DEP-16).
2. The lazy boot still reloads the FULL, verifiable history: after a restart that loads only tips,
   chain()/verify() materialize the whole chain from SQLite, verify passes, and a fresh seal continues
   the hash chain with the correct prev — so the memory fix costs nothing in correctness.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]  # apps/compute-gateway/tests -> repo root
sys.path.insert(0, str(_REPO / "tools"))                       # the shared gate harness
sys.path.insert(0, str(_REPO / "apps" / "compute-gateway" / "src"))  # compute_gateway (for spawn children)

from boot_memory_invariance import assert_boot_memory_invariant  # noqa: E402
from compute_gateway import persistence, receipts  # noqa: E402


# ── 1. boot memory is invariant to store size ──────────────────────────────────────────────────
def _seed_receipts(store: Path, n: int) -> None:
    """Write n receipts to a gateway.db. hydrate() reads only tips (project/id/seq in SQL) so the
    body content is immaterial here — what matters is that N rows exist to (not) load into RAM."""
    db = sqlite3.connect(store / "gateway.db")
    db.execute("CREATE TABLE IF NOT EXISTS receipts "
               "(project TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, "
               "PRIMARY KEY (project, seq))")
    body = json.dumps({"project": "demo", "kind": "graph-query", "prev": None, "ts": 0.0,
                       "pad": "x" * 512})  # ~0.5KB/receipt — a whole-store load would be unmistakable
    db.executemany("INSERT OR REPLACE INTO receipts (project, seq, id, body) VALUES (?,?,?,?)",
                   [("demo", i, f"sha256:{i:064x}", body) for i in range(n)])
    db.commit()
    db.close()


def _boot_hydrate(store: Path) -> None:
    """Boot the receipt store the way a restarted pod does: point at it and hydrate."""
    os.environ["GATEWAY_STORE_DIR"] = str(store)
    from compute_gateway import persistence as p, receipts as r
    p._reset_connection()
    r.hydrate()


def test_boot_memory_does_not_scale_with_receipt_count():
    # 64 vs 8192 receipts (128x): tips-only hydrate keeps the delta flat; the pre-fix hydrate that
    # built a Receipt per row would grow it ~linearly and blow the budget.
    assert_boot_memory_invariant(_seed_receipts, _boot_hydrate, small_n=64, large_n=8192, budget_kb=8192)


# ── 2. lazy boot preserves the full, verifiable chain across a restart ──────────────────────────
def _seal_n(project: str, n: int) -> list[str]:
    ids = []
    for i in range(n):
        r = receipts.seal(project, kind="graph-query", backend="hellgraph", runtime="gateway",
                          inputs={"i": i}, outputs={"i": i}, status="ok", actor="tester",
                          epistemic_status="attested")
        ids.append(r.id)
    return ids


def test_restart_reloads_full_verifiable_history_and_continues_the_chain():
    prev_env = os.environ.get("GATEWAY_STORE_DIR")
    with tempfile.TemporaryDirectory() as d:
        try:
            os.environ["GATEWAY_STORE_DIR"] = d
            persistence._reset_connection()
            receipts._CHAINS.clear()
            receipts._TIPS.clear()

            sealed = _seal_n("proj", 5)

            # Simulate a pod restart: drop every in-memory structure, reopen the store, hydrate.
            receipts._CHAINS.clear()
            receipts._TIPS.clear()
            persistence._reset_connection()
            receipts.hydrate()

            # Boot loaded only tips — the cache is empty until something reads it.
            assert "proj" not in receipts._CHAINS, "boot must not materialize any chain"
            assert receipts._TIPS["proj"].tip_id == sealed[-1]
            assert receipts._TIPS["proj"].count == 5

            # chain()/verify() lazily materialize the WHOLE history from SQLite and it verifies.
            ch = receipts.chain("proj")
            assert [r.id for r in ch] == sealed, "full chain reloads in seal order"
            v = receipts.verify("proj")
            assert v["valid"] and v["count"] == 5, v

            # A fresh seal continues the chain from the correct tip — prev links stay intact.
            sixth = receipts.seal("proj", kind="graph-query", backend="hellgraph", runtime="gateway",
                                  inputs={"i": 5}, outputs={"i": 5}, status="ok", actor="tester",
                                  epistemic_status="attested")
            assert sixth.prev == sealed[-1]
            assert receipts.verify("proj")["valid"], "chain still verifies after post-restart seal"
        finally:
            receipts._CHAINS.clear()
            receipts._TIPS.clear()
            if prev_env is None:
                os.environ.pop("GATEWAY_STORE_DIR", None)
            else:
                os.environ["GATEWAY_STORE_DIR"] = prev_env
            persistence._reset_connection()
            receipts.hydrate()
