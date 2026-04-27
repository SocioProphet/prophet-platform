from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from osm_map_api.main import create_app
from osm_map_api.receipt_digest import attach_digest, receipt_digest
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
        "provenance_refs": ["osm-binding-demo-way-424242"],
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


def assert_receipt(receipt: dict, *, response_kind: str, attribution: bool = True) -> None:
    assert receipt["receipt_version"] == "v0"
    assert receipt["service"] == "osm-map-api"
    assert receipt["response_kind"] == response_kind
    assert receipt["attribution"]["required"] is True
    assert receipt["integrity"]["signed"] is False
    assert receipt["integrity"]["canonicalization"] == "json-sort-keys-no-whitespace-v0"
    assert receipt["integrity"]["digest"].startswith("sha256:")
    assert receipt_digest(receipt) == receipt["integrity"]["digest"]
    if attribution:
        assert receipt["attribution"]["present"] is True
        assert "© OpenStreetMap contributors" in receipt["attribution"]["texts"]
        assert "ODbL-1.0" in receipt["attribution"]["license_refs"]
        assert receipt["provenance_refs_present"] is True


def test_receipt_digest_is_stable_and_ignores_existing_digest() -> None:
    receipt = {
        "receipt_version": "v0",
        "service": "osm-map-api",
        "response_kind": "test",
        "source_refs": ["osm://way/424242"],
        "provenance_refs_present": True,
        "attribution": {
            "required": True,
            "present": True,
            "texts": ["© OpenStreetMap contributors"],
            "license_refs": ["ODbL-1.0"],
        },
        "route_safety_status": "advisory",
        "safety_boundary": "OSM-derived routing is advisory unless separately validated.",
        "integrity": {"signed": False, "note": "unsigned"},
    }
    first = attach_digest(receipt)
    second = attach_digest({**first, "integrity": {**first["integrity"], "digest": "sha256:bad"}})
    assert first["integrity"]["digest"] == second["integrity"]["digest"]


def test_health_and_readiness(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_map_layer_catalog_preserves_attribution_and_receipts(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/map-layers")
    assert response.status_code == 200
    payload = response.json()
    layer = payload["layers"][0]
    assert layer["layer_id"] == "gaia-osm-demo-road-layer-v1"
    assert layer["attribution"]["attribution_text"] == "© OpenStreetMap contributors"
    assert layer["tiles"]["format"] == "mvt"
    assert_receipt(payload["response_receipt"], response_kind="map-layer-list")
    assert_receipt(layer["response_receipt"], response_kind="map-layer")


def test_feature_by_osm_and_h3_receipts(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    feature = client.get("/features/by-osm/way/424242").json()
    assert feature["osm_ref"]["osm_id"] == "424242"
    assert feature["gaia_ref"]["entity_id"] == "gaia-road-segment-demo-osm-way-424242"
    assert feature["response_receipt"]["route_safety_status"] == "advisory"
    assert_receipt(feature["response_receipt"], response_kind="osm-feature-binding")
    by_h3 = client.get("/features/by-h3/8928308280fffff").json()
    assert by_h3["features"]
    assert by_h3["layers"]
    assert_receipt(by_h3["response_receipt"], response_kind="h3-feature-layer-search")


def test_route_graph_is_advisory_with_receipts(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = client.get("/route-graphs/osm").json()
    assert payload["default_safety_status"] == "advisory"
    assert payload["route_graphs"][0]["safety_status"] == "advisory"
    assert payload["response_receipt"]["route_safety_status"] == "advisory"
    assert payload["route_graphs"][0]["response_receipt"]["route_safety_status"] == "advisory"
    assert_receipt(payload["response_receipt"], response_kind="osm-route-graph-list")


def test_runtime_governance_and_search_surfaces_with_receipts(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    runtime_payload = client.get("/runtime-boundaries/osm").json()
    runtimes = runtime_payload["runtimes"]
    assert {runtime["name"] for runtime in runtimes} == {
        "gaia-osm-ingestion-runtime",
        "gaia-osm-route-graph-runtime",
        "gaia-osm-tile-export-runtime",
    }
    assert_receipt(
        runtime_payload["response_receipt"],
        response_kind="osm-runtime-boundaries",
        attribution=False,
    )
    governance = client.get("/governance/osm").json()
    assert governance["attribution_required"] is True
    assert governance["validation_lanes"]
    assert_receipt(governance["response_receipt"], response_kind="osm-governance", attribution=False)
    search = client.get("/search/osm-demo").json()
    assert search["entity_type"] == "MAP_LAYER"
    assert search["actions"]["open_map"] is True
    assert_receipt(search["response_receipt"], response_kind="sherlock-osm-result", attribution=False)
    assert search["response_receipt"]["provenance_refs_present"] is True


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
