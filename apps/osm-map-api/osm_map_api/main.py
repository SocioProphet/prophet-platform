"""FastAPI entrypoint for the fixture-backed OSM Map API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

from .repository import ArtifactError, OSMArtifactRepository
from .settings import Settings


def repository(request: Request) -> OSMArtifactRepository:
    return request.app.state.repository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the OSM Map API application."""

    resolved_settings = settings or Settings.from_env()
    repo = OSMArtifactRepository(resolved_settings)

    app = FastAPI(
        title="Prophet Platform OSM Map API",
        version="0.1.0",
        description=(
            "Read-only fixture-backed API for OpenStreetMap-derived GAIA map layers, "
            "feature bindings, advisory route graphs, runtime-boundary state, and governance state."
        ),
    )
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
        return {"layers": layers}

    @app.get("/map-layers/{layer_id}", tags=["maps"])
    def map_layer(layer_id: str, request: Request) -> dict[str, Any]:
        try:
            layer = repository(request).map_layer(layer_id)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if layer is None:
            raise HTTPException(status_code=404, detail=f"map layer not found: {layer_id}")
        return layer

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
        return feature

    @app.get("/features/by-h3/{h3_cell}", tags=["features"])
    def features_by_h3(h3_cell: str, request: Request) -> dict[str, Any]:
        try:
            return repository(request).features_by_h3(h3_cell)
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/route-graphs/osm", tags=["routing"])
    def route_graphs_osm(request: Request) -> dict[str, Any]:
        try:
            route_graph = repository(request).osm_route_graph()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "route_graphs": [route_graph],
            "default_safety_status": "advisory",
            "safety_note": "OSM-derived route graphs are advisory unless separately validated.",
        }

    @app.get("/runtime-boundaries/osm", tags=["runtime"])
    def runtime_boundaries_osm(request: Request) -> dict[str, Any]:
        return repository(request).runtime_boundaries_osm()

    @app.get("/governance/osm", tags=["governance"])
    def governance_osm(request: Request) -> dict[str, Any]:
        try:
            return repository(request).governance_osm()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/search/osm-demo", tags=["search"])
    def search_osm_demo(request: Request) -> dict[str, Any]:
        try:
            return repository(request).sherlock_osm_result()
        except ArtifactError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
