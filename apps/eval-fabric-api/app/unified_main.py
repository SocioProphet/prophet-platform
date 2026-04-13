from __future__ import annotations

from fastapi import FastAPI

from . import governance_repositories, intelligence_repositories, repositories

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.5.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "eval-fabric-api"}


@app.get("/v1/frontier")
def frontier() -> dict:
    return {
        "profile_id": "profile.high_assurance_enterprise_agent",
        "subjects": repositories.get_frontier(),
        "source": "clickhouse",
        "provenance_mode": "trust-aware profile ranking",
    }


@app.get("/v1/frontier/provenance")
def frontier_provenance(limit: int = 50) -> dict:
    return {
        "subjects": intelligence_repositories.get_frontier_provenance(limit=limit),
        "source": "clickhouse",
    }


@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str) -> dict:
    return {
        "model_release_id": model_release_id,
        "metrics": repositories.get_model_dossier(model_release_id),
        "attribution": governance_repositories.get_model_attribution(model_release_id),
        "repro_ledger_entries": governance_repositories.get_model_repro_entries(model_release_id),
        "source": "clickhouse+postgres",
    }


@app.get("/v1/models/{model_release_id}/attribution")
def model_attribution(model_release_id: str, window: str = "rolling_30d") -> dict:
    return {
        "model_release_id": model_release_id,
        "window": window,
        "attribution": governance_repositories.get_model_attribution(model_release_id, window=window),
        "source": "postgres",
    }


@app.get("/v1/runs/{run_id}/provenance")
def run_provenance(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "provenance": governance_repositories.get_run_provenance(run_id),
        "source": "postgres",
    }


@app.get("/v1/governance/crosswalks")
def governance_crosswalks(limit: int = 50) -> dict:
    return {
        "crosswalks": governance_repositories.get_metric_crosswalks(limit=limit),
        "source": "postgres",
    }


@app.get("/v1/competition/reproduced-vs-claimed")
def reproduced_vs_claimed(limit: int = 50) -> dict:
    return {
        "items": intelligence_repositories.get_reproduced_vs_claimed(limit=limit),
        "source": "postgres",
    }


@app.get("/v1/competition/radar")
def radar() -> dict:
    return {
        "lane": "high_assurance_enterprise_agent",
        "competitors": repositories.get_competition_radar(),
        "source": "postgres",
    }
