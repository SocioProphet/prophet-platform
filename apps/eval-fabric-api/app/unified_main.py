from __future__ import annotations

from fastapi import FastAPI

from . import repositories

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.3.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "eval-fabric-api"}


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
