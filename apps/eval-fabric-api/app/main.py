from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response, status

from . import governance_repositories, intelligence_repositories, lifecycle_bundle, repositories
from .db import ch_health, pg_health
from .receipts import maybe_emit_artifacts

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.6.0")


def _attach_refs(response: Response, emission: Any | None) -> None:
    if emission is None:
        return
    response.headers["X-Payload-Ref"] = emission.payload_ref
    response.headers["X-Event-Envelope-Ref"] = emission.event_ref
    response.headers["X-Evidence-Receipt-Ref"] = emission.receipt_ref


def _emit(
    response: Response,
    *,
    event_type: str,
    action: str,
    subject_ref: str,
    payload: dict,
    scope_ref: str = "scope://platform/eval-fabric",
    classifiers: list[str] | None = None,
    metrics: dict | None = None,
) -> None:
    emission = maybe_emit_artifacts(
        event_type=event_type,
        action=action,
        status="succeeded",
        subject_ref=subject_ref,
        payload=payload,
        scope_ref=scope_ref,
        classifiers=classifiers or [],
        metrics=metrics or {},
    )
    _attach_refs(response, emission)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "eval-fabric-api", "mode": "canonical"}


@app.get("/readyz")
def readyz(response: Response) -> dict:
    postgres = pg_health()
    clickhouse = ch_health()
    ok = bool(postgres.get("ok")) and bool(clickhouse.get("ok"))
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
        "provenance_mode": "trust-aware profile ranking",
    }
    _emit(
        response,
        event_type="eval.fabric.frontier.read",
        action="FrontierQuery",
        subject_ref=f"profile://{payload['profile_id']}",
        payload=payload,
        classifiers=["route:frontier", "source:clickhouse"],
        metrics={"subject_count": len(payload["subjects"])}
    )
    return payload


@app.get("/v1/frontier/provenance")
def frontier_provenance(response: Response, limit: int = 50) -> dict:
    payload = {
        "subjects": intelligence_repositories.get_frontier_provenance(limit=limit),
        "source": "clickhouse",
    }
    _emit(
        response,
        event_type="eval.fabric.frontier.provenance.read",
        action="FrontierProvenanceQuery",
        subject_ref="profile://profile.high_assurance_enterprise_agent",
        payload=payload,
        classifiers=["route:frontier-provenance", "source:clickhouse"],
        metrics={"subject_count": len(payload["subjects"]), "limit": limit}
    )
    return payload


@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str, response: Response) -> dict:
    payload = {
        "model_release_id": model_release_id,
        "metrics": repositories.get_model_dossier(model_release_id),
        "attribution": governance_repositories.get_model_attribution(model_release_id),
        "repro_ledger_entries": governance_repositories.get_model_repro_entries(model_release_id),
        "source": "clickhouse+postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.dossier.read",
        action="DossierQuery",
        subject_ref=f"model://{model_release_id}",
        payload=payload,
        classifiers=["route:dossier", "source:clickhouse+postgres"],
        metrics={
            "metric_count": len(payload["metrics"]),
            "repro_entry_count": len(payload["repro_ledger_entries"]),
            "has_attribution": payload["attribution"] is not None,
        },
    )
    return payload


@app.get("/v1/models/{model_release_id}/attribution")
def model_attribution(model_release_id: str, response: Response, window: str = "rolling_30d") -> dict:
    payload = {
        "model_release_id": model_release_id,
        "window": window,
        "attribution": governance_repositories.get_model_attribution(model_release_id, window=window),
        "source": "postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.attribution.read",
        action="AttributionQuery",
        subject_ref=f"model://{model_release_id}",
        payload=payload,
        classifiers=["route:attribution", "source:postgres"],
        metrics={"window": window}
    )
    return payload


@app.get("/v1/models/{model_release_id}/lifecycle-bundle")
def model_lifecycle_bundle(model_release_id: str, response: Response) -> dict:
    payload = lifecycle_bundle.build_lifecycle_bundle(model_release_id=model_release_id)
    _emit(
        response,
        event_type="eval.fabric.lifecycle.bundle.read",
        action="LifecycleBundleQuery",
        subject_ref=f"model://{model_release_id}",
        payload=payload,
        classifiers=["route:lifecycle-bundle", "source:runtime+builders"],
        metrics={"artifact_count": 5},
    )
    return payload


@app.get("/v1/runs/{run_id}/provenance")
def run_provenance(run_id: str, response: Response) -> dict:
    payload = {
        "run_id": run_id,
        "provenance": governance_repositories.get_run_provenance(run_id),
        "source": "postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.run.provenance.read",
        action="RunProvenanceQuery",
        subject_ref=f"run://{run_id}",
        payload=payload,
        classifiers=["route:run-provenance", "source:postgres"],
    )
    return payload


@app.get("/v1/governance/crosswalks")
def governance_crosswalks(response: Response, limit: int = 50) -> dict:
    payload = {
        "crosswalks": governance_repositories.get_metric_crosswalks(limit=limit),
        "source": "postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.governance.crosswalks.read",
        action="GovernanceCrosswalksQuery",
        subject_ref="governance://metric-crosswalks",
        payload=payload,
        classifiers=["route:governance-crosswalks", "source:postgres"],
        metrics={"crosswalk_count": len(payload["crosswalks"]), "limit": limit}
    )
    return payload


@app.get("/v1/competition/reproduced-vs-claimed")
def reproduced_vs_claimed(response: Response, limit: int = 50) -> dict:
    payload = {
        "items": intelligence_repositories.get_reproduced_vs_claimed(limit=limit),
        "source": "postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.competition.coverage.read",
        action="CompetitionCoverageQuery",
        subject_ref="lane://high_assurance_enterprise_agent",
        payload=payload,
        classifiers=["route:reproduced-vs-claimed", "source:postgres"],
        metrics={"item_count": len(payload["items"]), "limit": limit}
    )
    return payload


@app.get("/v1/competition/radar")
def radar(response: Response) -> dict:
    payload = {
        "lane": "high_assurance_enterprise_agent",
        "competitors": repositories.get_competition_radar(),
        "source": "postgres",
    }
    _emit(
        response,
        event_type="eval.fabric.radar.read",
        action="RadarQuery",
        subject_ref="lane://high_assurance_enterprise_agent",
        payload=payload,
        classifiers=["route:radar", "source:postgres"],
        metrics={"competitor_count": len(payload["competitors"])}
    )
    return payload
