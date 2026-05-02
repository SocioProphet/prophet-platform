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


def make_fixture_roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    gaia = tmp_path / "gaia-world-model"
    sherlock = tmp_path / "sherlock-search"
    sociosphere = tmp_path / "sociosphere"
    catalog = tmp_path / "gaia-layer-catalog"

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

    layer_manifest_candidate = {
        "manifest_version": "v1",
        "manifest_kind": "osm-layer-manifest-candidate",
        "layer_id": "gaia-osm-bounded-road-layer-v1",
        "layer_type": "vector",
        "title": "GAIA OSM Bounded Road Layer (Ingest Candidate)",
        "production_tile_serving": False,
        "tile_serving_note": "Fixture-backed placeholder. Not production tile serving.",
        "sources": [{"source_id": "osm-bounded-ingest-demo", "source_type": "OpenStreetMap bounded extract"}],
        "tiles": {
            "url_template": "https://tiles.example.invalid/{z}/{x}/{y}.mvt",
            "format": "mvt",
            "min_zoom": 10,
            "max_zoom": 16,
            "note": "Placeholder MVT template. Not production tile serving.",
        },
        "spatial": {
            "bbox": [-74.012, 40.705, -73.998, 40.718],
            "crs": "EPSG:4326",
            "h3_cells": ["8928308280fffff", "8928308281fffff"],
        },
        "attribution": {
            "attribution_text": "© OpenStreetMap contributors",
            "license_refs": ["ODbL-1.0"],
            "source_urls": ["https://www.openstreetmap.org"],
            "attribution_required": True,
        },
        "provenance": {
            "source_refs": ["osm-feature-bindings.v1.json", "osm-source-receipt.v1.json"],
            "ingest_runner_ref": "gaia-world-model#17",
            "fixture_input_digest": "sha256:placeholder-bounded-ingest-input-digest-v1",
        },
        "classification": {
            "data_class": "public",
            "handling_tags": ["demo", "osm", "bounded-ingest", "fixture-backed"],
            "advisory_classification": "OSM-derived data is advisory.",
        },
        "status": {
            "freshness": "fresh",
            "generated_at": "2026-01-01T00:00:00Z",
            "stale_after": "2026-12-31T23:59:59Z",
        },
    }

    write_json(gaia / "fixtures/geospatial/osm-road-feature-binding.sample.v1.json", feature)
    write_json(gaia / "fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json", layer)
    write_json(gaia / "fixtures/geospatial/osm-route-graph.sample.v1.json", route_graph)
    write_json(sherlock / "examples/gaia-osm-derived-road-layer.sherlock-result.v1.json", search_result)
    write_json(sociosphere / "registry/gaia-ofif-meshlab-capability-map.v1.json", capability_map)
    write_json(
        catalog / "fixtures/geospatial/osm-layer-manifest-candidate.v1.json",
        layer_manifest_candidate,
    )
    return gaia, sherlock, sociosphere, catalog


def settings_for_roots(gaia: Path, sherlock: Path, sociosphere: Path, catalog: Path, **kwargs) -> Settings:
    return Settings(
        gaia_fixture_root=gaia,
        sherlock_fixture_root=sherlock,
        sociosphere_fixture_root=sociosphere,
        gaia_layer_catalog_root=catalog,
        **kwargs,
    )


def make_client(tmp_path: Path, **settings_kwargs) -> TestClient:
    gaia, sherlock, sociosphere, catalog = make_fixture_roots(tmp_path)
    app = create_app(settings_for_roots(gaia, sherlock, sociosphere, catalog, **settings_kwargs))
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


def test_cors_is_disabled_by_default(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.options(
        "/map-layers",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_vue_shell_origin(tmp_path: Path) -> None:
    client = make_client(
        tmp_path,
        cors_allowed_origins=("http://localhost:5174", "https://app.socioprophet.local"),
    )
    preflight = client.options(
        "/map-layers",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5174"
    response = client.get("/map-layers", headers={"Origin": "http://localhost:5174"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_cors_rejects_unlisted_browser_origin(tmp_path: Path) -> None:
    client = make_client(tmp_path, cors_allowed_origins=("http://localhost:5174",))
    preflight = client.options(
        "/map-layers",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


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


def test_healthz_is_live_when_readyz_fails(tmp_path: Path) -> None:
    """Liveness (/healthz) must return 200 even when readiness (/readyz) fails.

    This is a critical staging invariant: the process is alive and the probe
    infrastructure can distinguish a mis-configured data plane from a crashed
    process. Healthz must never depend on fixture root availability.
    """
    app = create_app(
        Settings(
            gaia_fixture_root=tmp_path / "missing-gaia",
            sherlock_fixture_root=tmp_path / "missing-sherlock",
            sociosphere_fixture_root=tmp_path / "missing-sociosphere",
        )
    )
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 503


def test_staging_https_cors_origin_is_allowed(tmp_path: Path) -> None:
    """A staging https origin is accepted when explicitly configured.

    Staging deployments set OSM_MAP_API_CORS_ALLOWED_ORIGINS to the staging
    app URL (https scheme, no wildcard). This test validates that pattern.
    """
    staging_origin = "https://staging.prophet.socioprophet.example"
    client = make_client(tmp_path, cors_allowed_origins=(staging_origin,))
    preflight = client.options(
        "/map-layers",
        headers={
            "Origin": staging_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == staging_origin
    response = client.get("/map-layers", headers={"Origin": staging_origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == staging_origin


def test_staging_cors_rejects_unconfigured_origin(tmp_path: Path) -> None:
    """An unlisted origin is rejected even in a staging CORS configuration."""
    staging_origin = "https://staging.prophet.socioprophet.example"
    client = make_client(tmp_path, cors_allowed_origins=(staging_origin,))
    preflight = client.options(
        "/map-layers",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


# ---------------------------------------------------------------------------
# GAIA layer catalog endpoint tests
# ---------------------------------------------------------------------------


def test_gaia_layer_catalog_returns_bounded_osm_layer(tmp_path: Path) -> None:
    """GET /gaia/layers returns the bounded OSM ingest manifest candidate."""
    client = make_client(tmp_path)
    response = client.get("/gaia/layers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["production_tile_serving"] is False
    assert "catalog_note" in payload
    layers = payload["layers"]
    assert len(layers) >= 1
    layer = layers[0]
    assert layer["layer_id"] == "gaia-osm-bounded-road-layer-v1"
    assert layer["layer_type"] == "vector"
    assert layer["manifest_kind"] == "osm-layer-manifest-candidate"
    assert_receipt(payload["response_receipt"], response_kind="gaia-layer-catalog")
    assert_receipt(layer["response_receipt"], response_kind="gaia-layer")


def test_gaia_layer_detail_returns_attribution_provenance_classification(tmp_path: Path) -> None:
    """GET /gaia/layers/{layer_id} exposes attribution, provenance, and classification."""
    client = make_client(tmp_path)
    response = client.get("/gaia/layers/gaia-osm-bounded-road-layer-v1")
    assert response.status_code == 200
    layer = response.json()
    # Attribution
    assert layer["attribution"]["attribution_text"] == "© OpenStreetMap contributors"
    assert "ODbL-1.0" in layer["attribution"]["license_refs"]
    assert layer["attribution"]["attribution_required"] is True
    # Provenance
    assert "osm-feature-bindings.v1.json" in layer["provenance"]["source_refs"]
    assert layer["provenance"]["ingest_runner_ref"] == "gaia-world-model#17"
    assert layer["provenance"]["fixture_input_digest"].startswith("sha256:")
    # Classification
    assert "fixture-backed" in layer["classification"]["handling_tags"]
    assert "osm" in layer["classification"]["handling_tags"]
    # Spatial / H3
    assert "8928308280fffff" in layer["spatial"]["h3_cells"]
    assert "bbox" in layer["spatial"]
    # Freshness
    assert layer["status"]["freshness"] == "fresh"
    assert_receipt(layer["response_receipt"], response_kind="gaia-layer")


def test_gaia_tile_manifest_returns_placeholder_mvt_url(tmp_path: Path) -> None:
    """GET /gaia/tile-manifests/{layer_id} returns non-production MVT placeholder."""
    client = make_client(tmp_path)
    response = client.get("/gaia/tile-manifests/gaia-osm-bounded-road-layer-v1")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["production_tile_serving"] is False
    assert "Not production tile serving" in manifest["tile_serving_note"]
    tiles = manifest["tiles"]
    assert "{z}" in tiles["url_template"]
    assert "{x}" in tiles["url_template"]
    assert "{y}" in tiles["url_template"]
    assert tiles["format"] == "mvt"
    assert tiles["url_template"].endswith(".mvt")
    # Ensure the placeholder URL does not claim a real endpoint
    assert ".invalid" in tiles["url_template"] or "example" in tiles["url_template"]
    assert_receipt(manifest["response_receipt"], response_kind="gaia-tile-manifest")


def test_gaia_unknown_layer_returns_404(tmp_path: Path) -> None:
    """Unknown layer_id returns a controlled 404 from /gaia/layers and /gaia/tile-manifests."""
    client = make_client(tmp_path)
    layer_response = client.get("/gaia/layers/does-not-exist")
    assert layer_response.status_code == 404
    assert "not found" in layer_response.json()["detail"].lower()

    tile_response = client.get("/gaia/tile-manifests/does-not-exist")
    assert tile_response.status_code == 404
    assert "not found" in tile_response.json()["detail"].lower()


def test_health_readiness_green_with_gaia_catalog(tmp_path: Path) -> None:
    """Health and readiness remain green when GAIA catalog root is configured."""
    client = make_client(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
