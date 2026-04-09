#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any


def apply_tql_live(tql: str, *, address: str | None = None, database: str | None = None) -> dict[str, Any]:
    resolved_address = address or os.environ.get("TYPEDB_ADDRESS", "127.0.0.1:1729")
    resolved_database = database or os.environ.get("TYPEDB_DATABASE")
    if not resolved_database:
        return {
            "ok": False,
            "mode": "typedb-live-apply",
            "address": resolved_address,
            "database": None,
            "tql": tql,
            "error": "TYPEDB_DATABASE not set",
        }
    try:
        from typedb.driver import TypeDB, SessionType, TransactionType
    except Exception as exc:
        return {
            "ok": False,
            "mode": "typedb-live-apply",
            "address": resolved_address,
            "database": resolved_database,
            "tql": tql,
            "error": f"typedb-driver unavailable: {exc}",
        }
    try:
        driver = TypeDB.core_driver(resolved_address)
        with driver:
            with driver.session(resolved_database, SessionType.DATA) as session:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(tql)
                    tx.commit()
        return {
            "ok": True,
            "mode": "typedb-live-apply",
            "address": resolved_address,
            "database": resolved_database,
            "tql": tql,
        }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "typedb-live-apply",
            "address": resolved_address,
            "database": resolved_database,
            "tql": tql,
            "error": str(exc),
        }
