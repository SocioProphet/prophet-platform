"""spark-runner contract + governance tests. The Spark execution (`run_sql`) and `spark_available` are injected,
so the HTTP contract, fail-closed gate, and receipt are verified without a Spark cluster; the real engine runs in
the deployed image."""
from fastapi.testclient import TestClient

import spark_runner.server as srv
from spark_runner.server import app

client = TestClient(app)


def test_healthz_reports_spark_state():
    b = client.get("/healthz").json()
    assert b["service"] == "spark-runner" and "spark_available" in b and b["master"]


def test_submit_fail_closed_without_token(monkeypatch):
    monkeypatch.setattr(srv, "SPARK_RUNNER_TOKEN", "")
    r = client.post("/v1/submit", json={"sql": "select 1"})
    assert r.status_code == 503   # fail-closed


def test_submit_503_when_spark_runtime_absent(monkeypatch):
    monkeypatch.setattr(srv, "SPARK_RUNNER_TOKEN", "T")
    monkeypatch.setattr(srv, "spark_available", lambda: False)
    r = client.post("/v1/submit", json={"sql": "select 1"}, headers={"Authorization": "Bearer T"})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]   # honest, never faked


def test_submit_rejects_empty_sql(monkeypatch):
    monkeypatch.setattr(srv, "SPARK_RUNNER_TOKEN", "T")
    r = client.post("/v1/submit", json={"sql": "   "}, headers={"Authorization": "Bearer T"})
    assert r.status_code == 422


def test_submit_runs_job_and_emits_governed_receipt(monkeypatch):
    monkeypatch.setattr(srv, "SPARK_RUNNER_TOKEN", "T")
    monkeypatch.setattr(srv, "spark_available", lambda: True)
    seen = {}

    def fake_run_sql(sql, rows, table):
        seen["sql"] = sql; seen["rows"] = rows; seen["table"] = table
        return [{"n": len(rows)}]                       # a canned aggregate result
    monkeypatch.setattr(srv, "run_sql", fake_run_sql)

    r = client.post("/v1/submit",
                    json={"sql": "select count(*) n from t", "data": [{"x": 1}, {"x": 2}, {"x": 3}], "table": "t"},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert r.status_code == 200 and b["row_count"] == 1 and b["rows"] == [{"n": 3}]
    assert seen["sql"].startswith("select count") and seen["table"] == "t" and len(seen["rows"]) == 3
    rec = b["receipt"]
    assert rec["engine"] == "apache-spark" and rec["input_rows"] == 3 and rec["output_rows"] == 1
    assert rec["replayable"] and rec["payload_sha256"] and "duration_ms" in rec
