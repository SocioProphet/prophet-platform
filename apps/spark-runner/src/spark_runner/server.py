"""spark-runner — the sovereign distributed-compute backend for the Studio execution plane.

The answer to "they run Spark, we don't": a real Apache Spark execution service. It runs a submitted SQL/
dataframe job on a Spark session (local[*] by default; SPARK_MASTER points it at a standalone/k8s cluster in
the paid mesh), and emits a governed, replayable receipt — input/output row counts, duration, and a payload
hash. lattice-studio's execution plane (backend="spark", once entitled) dispatches here.

Governance: fail-closed write token (SPARK_RUNNER_TOKEN). Degrades honestly — if the Spark runtime is not
present it returns 503, it never fakes a result. The Spark execution itself is behind `run_sql`, so the HTTP
contract + receipts are testable without a Spark cluster, while the real engine runs in the deployed image.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

SERVICE_VERSION = "0.1.0"
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")          # cluster URL in the mesh, or local
SPARK_RUNNER_TOKEN = os.getenv("SPARK_RUNNER_TOKEN", "")      # fail-closed submit gate
MAX_ROWS = int(os.getenv("SPARK_MAX_RESULT_ROWS", "10000"))

app = FastAPI(title="spark-runner", version=SERVICE_VERSION)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def spark_available() -> bool:
    try:
        import pyspark  # noqa: F401
        return True
    except ImportError:
        return False


_session: Any = None


def _get_session() -> Any:
    """Lazily create a single SparkSession (local[*] or the configured master)."""
    global _session
    if _session is None:
        from pyspark.sql import SparkSession
        _session = (SparkSession.builder
                    .appName("spark-runner")
                    .master(SPARK_MASTER)
                    .config("spark.ui.enabled", "false")
                    .getOrCreate())
    return _session


def run_sql(sql: str, rows: list[dict[str, Any]], table: str) -> list[dict[str, Any]]:
    """Execute a Spark SQL query over inline rows registered as a temp view. Real distributed compute — this is
    what runs in the deployed image. Isolated so the HTTP contract is testable without a Spark cluster."""
    spark = _get_session()
    df = spark.createDataFrame(rows) if rows else spark.createDataFrame([], schema="_empty string")
    df.createOrReplaceTempView(table)
    result = spark.sql(sql).limit(MAX_ROWS)
    return [r.asDict(recursive=True) for r in result.collect()]


def _require_token(authorization: str) -> None:
    if not SPARK_RUNNER_TOKEN:
        raise HTTPException(status_code=503, detail="spark-runner submit disabled: SPARK_RUNNER_TOKEN unset (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != SPARK_RUNNER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "spark-runner", "version": SERVICE_VERSION,
            "spark_available": spark_available(), "master": SPARK_MASTER}


class SubmitRequest(BaseModel):
    sql: str
    data: list[dict[str, Any]] = []       # inline rows registered as `table`
    table: str = "t"
    job_id: str | None = None


@app.post("/v1/submit")
async def submit(req: SubmitRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Run a Spark SQL job and return its rows + a governed, replayable receipt. Fail-closed on the token; 503 if
    the Spark runtime is unavailable (never a faked result)."""
    _require_token(authorization)
    if not req.sql.strip():
        raise HTTPException(status_code=422, detail="sql required")
    if not spark_available():
        raise HTTPException(status_code=503, detail="spark runtime unavailable (pyspark not installed in this image)")
    payload_hash = hashlib.sha256((req.sql + json.dumps(req.data, sort_keys=True, default=str)).encode()).hexdigest()
    correlation = req.job_id or f"spark-{payload_hash[:12]}"
    started = time.time()
    try:
        result = run_sql(req.sql, req.data, req.table)
    except Exception as exc:  # noqa: BLE001 — surface the Spark error to the caller, don't 500 opaquely
        raise HTTPException(status_code=400, detail=f"spark job failed: {type(exc).__name__}: {exc}") from exc
    duration_ms = int((time.time() - started) * 1000)
    receipt = {"correlation_id": correlation, "service": "spark-runner", "engine": "apache-spark",
               "master": SPARK_MASTER, "input_rows": len(req.data), "output_rows": len(result),
               "duration_ms": duration_ms, "payload_sha256": payload_hash, "replayable": True,
               "ran_at": _now_iso()}
    return {"job_id": correlation, "rows": result, "row_count": len(result), "receipt": receipt}
