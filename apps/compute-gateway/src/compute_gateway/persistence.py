"""Durable SQLite persistence for the compute plane's proof spine.

In-memory is the walking skeleton; this is what makes receipts and content-addressed
artifacts survive a restart, so a governed run stays replay-exact and auditable across
pod bounces — not just within one process. Without it the reconciled SQL facts persist
(the load sink) but the receipts, the signed chain, and the artifact blobs that back the
`insufficient-evidence`/`verified` verdicts evaporate on restart — the audit story with
them. Sovereign and no-bloat: one SQLite file, no external service; the zot/MinIO object
store drops in behind these same call sites when the estate wants it.

Enabled by GATEWAY_STORE_DIR. Unset ⇒ pure in-memory (tests, ephemeral dev) with ZERO
behaviour change: every function below no-ops or returns empty, so callers fall back to
their in-memory caches exactly as before. Each store hydrates its cache from here on boot
and writes through on every mutation. The store dir is read dynamically (not captured at
import) so a process can enable/point it before first use — which is what the tests do.

CONCURRENCY: one SQLite file wants one writer. Enable this only where the gateway runs
single-replica on a ReadWriteOnce volume — which is already the honest posture, since the
in-memory store is per-pod today (a 2-replica gateway already returns different chains per
pod). For a multi-writer HA gateway the same call sites take the zot/MinIO object backend
instead; nothing above changes.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None
_OPENED_FOR: str | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
  project TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (project, seq));
CREATE TABLE IF NOT EXISTS blobs (digest TEXT PRIMARY KEY, blob TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifact_index (
  receipt_id TEXT NOT NULL, ord INTEGER NOT NULL, digest TEXT NOT NULL,
  PRIMARY KEY (receipt_id, ord));
"""


def store_dir() -> str:
    return os.getenv("GATEWAY_STORE_DIR", "").strip()


def enabled() -> bool:
    return bool(store_dir())


def _conn() -> sqlite3.Connection:
    """Lazily open (and, on a store-dir change, re-open) the WAL-mode SQLite file."""
    global _CONN, _OPENED_FOR
    d = store_dir()
    if _CONN is not None and _OPENED_FOR == d:
        return _CONN
    if _CONN is not None:
        _CONN.close()
    os.makedirs(d, exist_ok=True)
    _CONN = sqlite3.connect(os.path.join(d, "gateway.db"), check_same_thread=False)
    _CONN.execute("PRAGMA journal_mode=WAL")
    _CONN.executescript(_SCHEMA)
    _CONN.commit()
    _OPENED_FOR = d
    return _CONN


# ── receipts (the hash-chained proof spine) ──────────────────────────────────
def load_receipts() -> dict[str, list[dict]]:
    """Every project's chain in seal order — the caller rebuilds Receipt objects."""
    if not enabled():
        return {}
    out: dict[str, list[dict]] = {}
    for project, body in _conn().execute(
            "SELECT project, body FROM receipts ORDER BY project, seq").fetchall():
        out.setdefault(project, []).append(json.loads(body))
    return out


def save_receipt(project: str, seq: int, receipt_id: str, body_json: str) -> None:
    if not enabled():
        return
    with _LOCK:
        c = _conn()
        c.execute("INSERT OR REPLACE INTO receipts (project, seq, id, body) VALUES (?,?,?,?)",
                  (project, seq, receipt_id, body_json))
        c.commit()


# ── content-addressed artifact blobs + the receipt→digests index ─────────────
def get_blob(d: str) -> Any | None:
    if not enabled():
        return None
    row = _conn().execute("SELECT blob FROM blobs WHERE digest=?", (d,)).fetchone()
    return json.loads(row[0]) if row else None


def has_blob(d: str) -> bool:
    if not enabled():
        return False
    return _conn().execute("SELECT 1 FROM blobs WHERE digest=?", (d,)).fetchone() is not None


def save_blob(d: str, blob: Any) -> None:
    if not enabled():
        return
    with _LOCK:
        c = _conn()
        c.execute("INSERT OR IGNORE INTO blobs (digest, blob) VALUES (?,?)",
                  (d, json.dumps(blob, sort_keys=True, default=str, ensure_ascii=False)))
        c.commit()


def load_index() -> dict[str, list[str]]:
    if not enabled():
        return {}
    out: dict[str, list[str]] = {}
    for rid, digest in _conn().execute(
            "SELECT receipt_id, digest FROM artifact_index ORDER BY receipt_id, ord").fetchall():
        out.setdefault(rid, []).append(digest)
    return out


def save_index(receipt_id: str, digests: list[str]) -> None:
    if not enabled():
        return
    with _LOCK:
        c = _conn()
        c.executemany("INSERT OR REPLACE INTO artifact_index (receipt_id, ord, digest) VALUES (?,?,?)",
                      [(receipt_id, i, d) for i, d in enumerate(digests)])
        c.commit()


def _reset_connection() -> None:
    """Test hook — drop the cached handle so the next call re-opens (simulates a restart)."""
    global _CONN, _OPENED_FOR
    if _CONN is not None:
        _CONN.close()
    _CONN = None
    _OPENED_FOR = None
