from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

try:
    import clickhouse_connect
except Exception:  # pragma: no cover
    clickhouse_connect = None

app = FastAPI(title="Prophet Platform Eval Fabric (Persisted)", version="0.2.0")

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://prophet:prophet@localhost:5432/prophet_platform")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")


def _pg_fetch(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed")
    with psycopg.connect(POSTGRES_DSN) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def _ch_query(sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if clickhouse_connect is None:
        raise RuntimeError("clickhouse-connect is not installed")
    client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT, database=CLICKHOUSE_DATABASE)
    result = client.query(sql, parameters=parameters or {})
    cols = list(result.column_names)
    return [dict(zip(cols, row)) for row in result.result_rows]


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "ok", "service": "eval-fabric-api-persisted"}
    try:
        payload["postgres"] = {"ok": len(_pg_fetch("select 1 as ok")) == 1}
    except Exception as exc:  # pragma: no cover
        payload["postgres"] = {"ok": False, "error": str(exc)}
    try:
        payload["clickhouse"] = {"ok": len(_ch_query("select 1 as ok")) == 1}
    except Exception as exc:  # pragma: no cover
        payload["clickhouse"] = {"ok": False, "error": str(exc)}
    return payload


@app.get("/v1/frontier")
def frontier() -> dict[str, Any]:
    rows = _ch_query(
        """
        select profile_id, subject_id, score, rank, score_policy_id
        from profile_scores
        where profile_id = 'profile.high_assurance_enterprise_agent'
        order by rank asc, score desc
        limit 20
        """
    )
    return {
        "profile_id": "profile.high_assurance_enterprise_agent",
        "subjects": rows,
        "source": "clickhouse"
    }


@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str) -> dict[str, Any]:
    rows = _ch_query(
        """
        select metric_definition_id, value_scalar, sample_n, trial_count, ts
        from metric_facts
        where model_release_id = {model_release_id:String}
        order by ts desc
        limit 50
        """,
        {"model_release_id": model_release_id},
    )
    return {
        "model_release_id": model_release_id,
        "metrics": rows,
        "source": "clickhouse"
    }


@app.get("/v1/competition/radar")
def radar() -> dict[str, Any]:
    rows = _pg_fetch(
        """
        select competitor_snapshot_id, provider_id, model_release_id,
               freshness_days, source_trust_class, strategic_relevance
        from competitor_snapshots
        order by strategic_relevance desc, freshness_days asc, snapshot_ts desc
        limit 50
        """
    )
    return {
        "lane": "high_assurance_enterprise_agent",
        "competitors": rows,
        "source": "postgres"
    }
