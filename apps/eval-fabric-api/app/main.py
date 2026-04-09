from __future__ import annotations

from fastapi import FastAPI, Response, status

from . import repositories
from .db import ch_health, pg_health

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.4.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "eval-fabric-api", "mode": "unified"}


@app.get("/readyz")
def readyz(response: Response) -> dict:
    postgres = pg_health()
    clickhouse = ch_health()
    ok = postgres.get("ok") and clickhouse.get("ok")
    response.status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if ok else "degraded",
        "service": "eval-fabric-api",
        "postgres": postgres,
        "clickhouse": clickhouse,
    }


@app.get("/v1/frontier")
def frontier() -> dict:
    return {
        "profile_id": "profile.high_assurance_enterprise_agent",
        "subjects": repositories.get_frontier(),
        "source": "clickhouse",
    }


@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str) -> dict:
    return {
        "model_release_id": model_release_id,
        "metrics": repositories.get_model_dossier(model_release_id),
        "source": "clickhouse",
    }


@app.get("/v1/competition/radar")
def radar() -> dict:
    return {
        "lane": "high_assurance_enterprise_agent",
        "competitors": repositories.get_competition_radar(),
        "source": "postgres",
    }
