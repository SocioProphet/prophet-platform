#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_sql(value: Any) -> str:
    return _sql_string(json.dumps(value, sort_keys=True, separators=(",", ":")))


def build_insert_sql(observation: dict[str, Any]) -> str:
    cols = [
        "observation_id",
        "source_system",
        "source_record_id",
        "observed_at",
        "normalized_payload",
        "trust_class",
        "content_hash",
        "identity_hash",
        "lineage_hash",
        "state",
        "created_at",
    ]
    vals = [
        _sql_string(observation["observation_id"]),
        _sql_string(observation["source_system"]),
        _sql_string(observation.get("source_record_id", "")),
        _sql_string(observation["observed_at"]),
        _json_sql(observation["normalized_payload"]),
        _sql_string(observation.get("trust_class", "")),
        _sql_string(observation["content_hash"]),
        _sql_string(observation["identity_hash"]),
        _sql_string(observation.get("lineage_hash", "")),
        _sql_string(observation["state"]),
        _sql_string(observation["created_at"]),
    ]
    return f"INSERT INTO observations ({', '.join(cols)}) VALUES ({', '.join(vals)});"


def insert_observation(observation: dict[str, Any], *, dolt_dir: str | None = None) -> dict[str, Any]:
    workdir = Path(dolt_dir or os.environ.get("DOLT_DB_DIR", ".")).resolve()
    sql = build_insert_sql(observation)
    try:
        proc = subprocess.run(
            ["dolt", "sql", "-q", sql],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "mode": "dolt-cli",
            "cwd": str(workdir),
            "sql": sql,
            "error": "dolt binary not found",
        }
    return {
        "ok": proc.returncode == 0,
        "mode": "dolt-cli",
        "cwd": str(workdir),
        "sql": sql,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
    }
