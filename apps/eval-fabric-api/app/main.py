from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response, status

from . import repositories
from .db import ch_health, pg_health
from .receipts import maybe_emit_artifacts

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.5.0")


def _attach_refs(response: Response, emission: Any | None) -> None:
    if emission is None:
        return
    response.headers["X-Payload-Ref"] = emission.payload_ref
    response.headers["X-Event-Envelope-Ref"] = emission.event_ref
    response.headers["X-Evidence-Receipt-Ref"] = emission.receipt_ref


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
def frontier(response: Response) -> dict:
    payload = {
        "profile_id": "profile.high_assurance_enterprise_agent",
        "subjects": repositories.get_frontier(),
        "source": "clickhouse",
    }
    emission = maybe_emit_artifacts(
        event_type="eval.fabric.frontier.read",
        action="FrontierQuery",
        status="succeeded",
        subject_ref=f"profile://{payload['profile_id']}",
        payload=payload,
        scope_ref="scope://platform/eval-fabric",
        classifiers=["route:frontier", "source:clickhouse"],
        metrics={"subject_count": len(payload["subjects"])}
    )
    _attach_refs(response, emission)
    return payload


@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str, response: Response) -> dict:
    payload = {
        "model_release_id": model_release_id,
        "metrics": repositories.get_model_dossier(model_release_id),
        "source": "clickhouse",
    }
    emission = maybe_emit_artifacts(
        event_type="eval.fabric.dossier.read",
        action="DossierQuery",
        status="succeeded",
        subject_ref=f"model://{model_release_id}",
        payload=payload,
        scope_ref="scope://platform/eval-fabric",
        classifiers=["route:dossier", "source:clickhouse"],
        metrics={"metric_count": len(payload["metrics"])}
    )
    _attach_refs(response, emission)
    return payload


@app.get("/v1/competition/radar")
def radar(response: Response) -> dict:
    payload = {
        "lane": "high_assurance_enterprise_agent",
        "competitors": repositories.get_competition_radar(),
        "source": "postgres",
    }
    emission = maybe_emit_artifacts(
        event_type="eval.fabric.radar.read",
        action="RadarQuery",
        status="succeeded",
        subject_ref="lane://high_assurance_enterprise_agent",
        payload=payload,
        scope_ref="scope://platform/eval-fabric",
        classifiers=["route:radar", "source:postgres"],
        metrics={"competitor_count": len(payload["competitors"])}
    )
    _attach_refs(response, emission)
    return payload
