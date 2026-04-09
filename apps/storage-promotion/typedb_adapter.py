#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def _escape(value: str) -> str:
    return value.replace('"', '\\"')


def build_insert_tql(promoted: dict) -> str:
    entities = promoted["entities"]
    claim = promoted["claim"]
    user = entities[0]
    role = entities[1]
    return "\n".join([
        "insert",
        f'$u isa semantic-entity, has object-id "{_escape(user["id"])}", has kind "{_escape(user["kind"])}", has name "{_escape(user["name"])}";',
        f'$r isa semantic-entity, has object-id "{_escape(role["id"])}", has kind "{_escape(role["kind"])}", has name "{_escape(role["name"])}";',
        f'$c isa claim-record, has object-id "{_escape(claim["id"])}", has kind "{_escape(claim["type"])}", has confidence 1.0;',
        f'(assertion-subject: $u, assertion-object: $r) isa semantic-assertion, has kind "{_escape(claim["type"])}", has confidence 1.0;',
    ])


def persist_tql(tql: str, *, out_path: str | None = None) -> dict:
    target = Path(out_path or os.environ.get("TYPEDB_TQL_OUT", "typedb_insert.tql")).resolve()
    target.write_text(tql + "\n", encoding="utf-8")
    return {
        "ok": True,
        "mode": "typedb-tql-export",
        "path": str(target),
    }
