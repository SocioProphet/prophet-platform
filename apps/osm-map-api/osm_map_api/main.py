"""FastAPI entrypoint for the fixture-backed OSM Map API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .gaia_layer_catalog import (
    gaia_layer as catalog_gaia_layer,
    gaia_layers as catalog_gaia_layers,
    gaia_tile_manifest as catalog_gaia_tile_manifest,
)
from .receipts import response_receipt, with_artifact_receipt
from .repository import ArtifactError, OSMArtifactRepository
from .settings import Settings


def repository(request: Request) -> OSMArtifactRepository:
    return request.app.state.repository


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    """Enable browser access only when allowed origins are configured."""

    if not settings.cors_allowed_origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Content-Type"],
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the OSM Map API application."""

    resolved_settings = settings or Settings.from_env()
    repo = OSMArtifactRepository(resolved_settings)

    app = FastAPI(
        title="Prophet Platform OSM Map API",
        version="0.1.0",
        description=(
            "Read-only fixture-backed API for OpenStreetMap-derived GAIA map layers, "
            "feature bindings, advisory route graphs, attribution receipts, runtime-boundary "
            "state, provenance state, governance state, and fixture-backed GAIA layer catalog "
            "metadata. GAIA tile-manifest responses expose production_tile_serving=false to "
            "make the non-production tile boundary machine visible."
        ),
    )
    _configure_cors(app, resolved_settings)
    app.state.repository = repo

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    def readyz(request: Request) -> dict[str, Any]:
        errors = repository(request).readiness_errors()
        if errors:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not-ready", "errors": errors},
            )
        return {"status": "ready"}

    @app.get("/map-layers", tags=["maps"])
    def map_layers(request: Request) -> dict[str, Any]:
        try:
            layers = repository(request).map_layers()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "layers": [with_artifact_receipt("map-layer", layer) for layer in layers],
            "response_receipt": response_receipt("map-layer-list", layers),
        }

    @app.get("/map-layers/{layer_id}", tags=["maps"])
    def map_layer(layer_id: str, request: Request) -> dict[str, Any]:
        try:
            layer = repository(request).map_layer(layer_id)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if layer is None:
            raise HTTPException(status_code=404, detail=f"map layer not found: {layer_id}")
        return with_artifact_receipt("map-layer", layer)

    @app.get("/gaia/layers", tags=["gaia"])
    def gaia_layers(request: Request) -> dict[str, Any]:
        try:
            layers = catalog_gaia_layers(repository(request))
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "layers": [with_artifact_receipt("gaia-layer", layer) for layer in layers],
            "catalog_mode": "fixture-backed",
            "production_tile_serving": False,
            "response_receipt": response_receipt("gaia-layer-list", layers),
        }

    @app.get("/gaia/layers/{layer_id}", tags=["gaia"])
    def gaia_layer(layer_id: str, request: Request) -> dict[str, Any]:
        try:
            layer = catalog_gaia_layer(repository(request), layer_id)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if layer is None:
            raise HTTPException(status_code=404, detail=f"GAIA layer not found: {layer_id}")
        return with_artifact_receipt("gaia-layer", layer)

    @app.get("/gaia/tile-manifests/{layer_id}", tags=["gaia"])
    def gaia_tile_manifest(layer_id: str, request: Request) -> dict[str, Any]:
        try:
            manifest = catalog_gaia_tile_manifest(repository(request), layer_id)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if manifest is None:
            raise HTTPException(
                status_code=404,
                detail=f"GAIA tile manifest not found: {layer_id}",
            )
        return with_artifact_receipt("gaia-tile-manifest", manifest)

    @app.get("/features/by-osm/{osm_type}/{osm_id}", tags=["features"])
    def feature_by_osm(osm_type: str, osm_id: str, request: Request) -> dict[str, Any]:
        try:
            feature = repository(request).feature_by_osm(osm_type, osm_id)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if feature is None:
            raise HTTPException(
                status_code=404,
                detail=f"feature not found for OSM ref: {osm_type}/{osm_id}",
            )
        return with_artifact_receipt("osm-feature-binding", feature)

    @app.get("/features/by-h3/{h3_cell}", tags=["features"])
    def features_by_h3(h3_cell: str, request: Request) -> dict[str, Any]:
        try:
            payload = repository(request).features_by_h3(h3_cell)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        artifacts = [*payload.get("features", []), *payload.get("layers", [])]
        payload["response_receipt"] = response_receipt("h3-feature-layer-search", artifacts)
        return payload

    @app.get("/route-graphs/osm", tags=["routing"])
    def route_graphs_osm(request: Request) -> dict[str, Any]:
        try:
            route_graph = repository(request).osm_route_graph()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "route_graphs": [with_artifact_receipt("osm-route-graph", route_graph)],
            "default_safety_status": "advisory",
            "safety_note": "OSM-derived route graphs are advisory unless separately validated.",
            "response_receipt": response_receipt("osm-route-graph-list", [route_graph]),
        }

    @app.get("/runtime-boundaries/osm", tags=["runtime"])
    def runtime_boundaries_osm(request: Request) -> dict[str, Any]:
        payload = repository(request).runtime_boundaries_osm()
        payload["response_receipt"] = response_receipt("osm-runtime-boundaries", [])
        return payload

    @app.get("/governance/osm", tags=["governance"])
    def governance_osm(request: Request) -> dict[str, Any]:
        try:
            payload = repository(request).governance_osm()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        payload["response_receipt"] = response_receipt("osm-governance", [])
        return payload

    @app.get("/search/osm-demo", tags=["search"])
    def search_osm_demo(request: Request) -> dict[str, Any]:
        try:
            result = repository(request).sherlock_osm_result()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        result["response_receipt"] = response_receipt("sherlock-osm-result", [result])
        return result

    return app


app = create_app()
