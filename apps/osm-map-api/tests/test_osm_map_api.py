from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from osm_map_api.main import create_app
from osm_map_api.settings import Settings


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def make_fixture_roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    gaia = tmp_path / "gaia-world-model"
    sherlock = tmp_path / "sherlock-search"
    sociosphere = tmp_path / "sociosphere"

    feature = {
        "binding_version": "v1",
        "binding_id": "osm-binding-demo-way-424242",
        "source": "OpenStreetMap",
        "osm_ref": {
            "osm_type": "way",
            "osm_id": "424242",
            "tags": {"highway": "residential", "name": "Demo Corridor Road"},
        },
        "gaia_ref": {
            "entity_id": "gaia-road-segment-demo-osm-way-424242",
            "entity_type": "RoadSegment",
        },
        "spatial": {
            "geometry_ref": "geometry://demo/osm/way/424242",
            "h3_cells": ["8928308280fffff"],
            "bbox": [-74.012, 40.705, -73.998, 40.718],
            "crs": "EPSG:4326",
        },
        "routing": {"routable": True, "modes": ["road"], "safety_status": "advisory"},
        "attribution": {
            "attribution_text": "© OpenStreetMap contributors",
            "license_ref": "ODbL-1.0",
            "source_url": "https://www.openstreetmap.org",
        },
        "provenance": {"source_refs": ["osm://way/424242"]},
        "classification": {"data_class": "public", "handling_tags": ["demo", "osm"]},
    }

    layer = {
        "manifest_version": "v1",
        "layer_id": "gaia-osm-demo-road-layer-v1",
        "layer_type": "vector",
        "title": "GAIA OSM Demo Road Layer",
        "sources": [{"source_id": "osm-demo", "source_type": "OpenStreetMap extract"}],
        "tiles": {"url_template": "https://tiles.example/{z}/{x}/{y}.mvt", "format": "mvt"},
        "spatial": {"h3_cells": ["8928308280fffff"]},
        "attribution": {
            "attribution_text": "© OpenStreetMap contributors",
            "license_refs": ["ODbL-1.0"],
            "source_urls": ["https://www.openstreetmap.org"],
        },
        "provenance": {"source_refs": ["osm-binding-demo-way-424242"]},
        "classification": {"data_class": "public", "handling_tags": ["demo", "osm"]},
    }

    route_graph = {
        "manifest_version": "v1",
        "graph_id": "gaia-osm-route-graph-way-424242-v1",
        "source": "OpenStreetMap",
        "safety_status": "advisory",
        "nodes": [{"node_id": "start", "geometry_ref": "geometry://start"}],
        "edges": [
            {
                "edge_id": "edge-1",
                "from_node": "start",
                "to_node": "end",
                "feature_ref": "gaia-road-segment-demo-osm-way-424242",
                "geometry_ref": "geometry://demo/osm/way/424242",
                "safety_status": "advisory",
            }
        ],
        "attribution": {
            "attribution_text": "© OpenStreetMap contributors",
            "license_refs": ["ODbL-1.0"],
        },
        "provenance": {"source_refs": ["osm-binding-demo-way-424242"]},
        "classification": {"data_class": "public", "handling_tags": ["demo", "osm"]},
    }

    search_result = {
        "record_version": "v1",
        "result_id": "search-gaia-osm-demo-road-layer-v1",
        "source": "GAIA",
        "entity_type": "MAP_LAYER",
        "title": "GAIA OSM Demo Road Layer",
        "spatial_refs": [{"scheme": "osm", "value": "way/424242"}],
        "actions": {"open_map": True},
    }

    capability_map = {
        "registry_version": "v1",
        "capability_program": "gaia-ofif-meshlab-control-tower",
        "validation_lanes": [
            {"id": "gaia-openstreetmap-bindings", "repo": "gaia-world-model", "state": "ci-defined"}
        ],
    }

    write_json(gaia / "fixtures/geospatial/osm-road-feature-binding.sample.v1.json", feature)
    write_json(gaia / "fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json", layer)
    write_json(gaia / "fixtures/geospatial/osm-route-graph.sample.v1.json", route_graph)
    write_json(sherlock / "examples/gaia-osm-derived-road-layer.sherlock-result.v1.json", search_result)
    write_json(sociosphere / "registry/gaia-ofif-meshlab-capability-map.v1.json", capability_map)
    return gaia, sherlock, sociosphere


def make_client(tmp_path: Path) -> TestClient:
    gaia, sherlock, sociosphere = make_fixture_roots(tmp_path)
    app = create_app(
        Settings(
            gaia_fixture_root=gaia,
            sherlock_fixture_root=sherlock,
            sociosphere_fixture_root=sociosphere,
        )
    )
    return TestClient(app)


def test_health_and_readiness(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_map_layer_catalog_preserves_attribution(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/map-layers")
    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert layer["layer_id"] == "gaia-osm-demo-road-layer-v1"
    assert layer["attribution"]["attribution_text"] == "© OpenStreetMap contributors"
    assert layer["tiles"]["format"] == "mvt"


def test_feature_by_osm_and_h3(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    feature = client.get("/features/by-osm/way/424242").json()
    assert feature["osm_ref"]["osm_id"] == "424242"
    assert feature["gaia_ref"]["entity_id"] == "gaia-road-segment-demo-osm-way-424242"
    by_h3 = client.get("/features/by-h3/8928308280fffff").json()
    assert by_h3["features"]
    assert by_h3["layers"]


def test_route_graph_is_advisory(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = client.get("/route-graphs/osm").json()
    assert payload["default_safety_status"] == "advisory"
    assert payload["route_graphs"][0]["safety_status"] == "advisory"


def test_runtime_governance_and_search_surfaces(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    runtimes = client.get("/runtime-boundaries/osm").json()["runtimes"]
    assert {runtime["name"] for runtime in runtimes} == {
        "gaia-osm-ingestion-runtime",
        "gaia-osm-route-graph-runtime",
        "gaia-osm-tile-export-runtime",
    }
    governance = client.get("/governance/osm").json()
    assert governance["attribution_required"] is True
    assert governance["validation_lanes"]
    search = client.get("/search/osm-demo").json()
    assert search["entity_type"] == "MAP_LAYER"
    assert search["actions"]["open_map"] is True


def test_missing_roots_fail_readiness(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            gaia_fixture_root=tmp_path / "missing-gaia",
            sherlock_fixture_root=tmp_path / "missing-sherlock",
            sociosphere_fixture_root=tmp_path / "missing-sociosphere",
        )
    )
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "not-ready"
