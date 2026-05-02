from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from osm_map_api.main import create_app
from osm_map_api.settings import Settings

from test_osm_map_api import assert_receipt, make_fixture_roots, write_json

BOUNDED_LAYER_ID = "osm-layer-manifest-candidate-lower-manhattan-bounded-extract-2026-04-26"
FIXTURE_DIGEST = "sha256:e5baba1a98e0e59887bf19fe840b0544904f23d05e5fb9989a9f53f86d1b360b"


def make_gaia_catalog_client(tmp_path: Path) -> TestClient:
    gaia, sherlock, sociosphere = make_fixture_roots(tmp_path)
    layer_manifest = {
        "manifest_version": "v1",
        "layer_id": BOUNDED_LAYER_ID,
        "layer_type": "vector",
        "title": "GAIA OSM Bounded Ingest Layer – Lower Manhattan Bounded Extract",
        "description": "Bounded OSM ingest layer manifest candidate. Fixture-backed API catalog surface. Not production tile-serving. Advisory only.",
        "sources": [
            {
                "source_id": "osm-source-envelope-lower-manhattan-bounded-extract-2026-04-26",
                "source_type": "OpenStreetMap extract",
                "source_refs": [
                    "osm-extract://bounded/lower-manhattan/2026-04-26",
                    "osm-source-receipt.v1.json",
                    "osm-feature-bindings.v1.json",
                ],
            }
        ],
        "tiles": {
            "url_template": "placeholder://tiles/gaia/osm-bounded/{z}/{x}/{y}.mvt",
            "min_zoom": 0,
            "max_zoom": 14,
            "format": "mvt",
        },
        "spatial": {
            "bbox": [-74.012, 40.705, -73.998, 40.718],
            "h3_cells": ["89283082807ffff", "8928308280fffff", "8928308281fffff"],
            "crs": "EPSG:4326",
        },
        "attribution": {
            "attribution_text": "© OpenStreetMap contributors",
            "license_refs": ["ODbL-1.0"],
            "source_urls": ["https://www.openstreetmap.org"],
        },
        "provenance": {
            "source_refs": [
                "osm-source-receipt.v1.json",
                "osm-feature-bindings.v1.json",
                "osm-extract://bounded/lower-manhattan/2026-04-26",
            ],
            "fixture_digest": FIXTURE_DIGEST,
            "runtime_refs": ["gaia-bounded-osm-ingest-runner@v1"],
            "created_at": "2026-04-27T06:10:00Z",
            "content_hash": "sha256:ae4f4d078e81de81fd413ad2f243f250af99bc268580143801fa18875214c5d9",
        },
        "classification": {
            "data_class": "public",
            "handling_tags": ["demo", "osm", "bounded-extract", "geospatial", "advisory"],
        },
    }
    write_json(
        gaia / "examples/osm-bounded-ingest/osm-layer-manifest-candidate.v1.json",
        layer_manifest,
    )
    app = create_app(
        Settings(
            gaia_fixture_root=gaia,
            sherlock_fixture_root=sherlock,
            sociosphere_fixture_root=sociosphere,
        )
    )
    return TestClient(app)


def test_gaia_layer_catalog_lists_bounded_osm_layer(tmp_path: Path) -> None:
    client = make_gaia_catalog_client(tmp_path)
    payload = client.get("/gaia/layers").json()

    assert payload["catalog_mode"] == "fixture-backed"
    assert payload["production_tile_serving"] is False
    assert len(payload["layers"]) == 1
    layer = payload["layers"][0]
    assert layer["layer_id"] == BOUNDED_LAYER_ID
    assert layer["tiles"]["url_template"].startswith("placeholder://")
    assert layer["provenance"]["fixture_digest"] == FIXTURE_DIGEST
    assert layer["classification"]["data_class"] == "public"
    assert "ODbL-1.0" in layer["attribution"]["license_refs"]
    assert_receipt(payload["response_receipt"], response_kind="gaia-layer-list")
    assert_receipt(layer["response_receipt"], response_kind="gaia-layer")


def test_gaia_layer_detail_preserves_attribution_and_provenance(tmp_path: Path) -> None:
    client = make_gaia_catalog_client(tmp_path)
    response = client.get(f"/gaia/layers/{BOUNDED_LAYER_ID}")

    assert response.status_code == 200
    layer = response.json()
    assert layer["spatial"]["bbox"] == [-74.012, 40.705, -73.998, 40.718]
    assert "8928308280fffff" in layer["spatial"]["h3_cells"]
    assert "osm-source-receipt.v1.json" in layer["provenance"]["source_refs"]
    assert "© OpenStreetMap contributors" in layer["attribution"]["attribution_text"]
    assert layer["classification"]["handling_tags"][-1] == "advisory"
    assert_receipt(layer["response_receipt"], response_kind="gaia-layer")


def test_gaia_tile_manifest_is_explicitly_non_production(tmp_path: Path) -> None:
    client = make_gaia_catalog_client(tmp_path)
    response = client.get(f"/gaia/tile-manifests/{BOUNDED_LAYER_ID}")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["layer_id"] == BOUNDED_LAYER_ID
    assert manifest["production_tile_serving"] is False
    assert manifest["tile_serving_status"] == "fixture-placeholder-not-production"
    assert manifest["tiles"]["format"] == "mvt"
    assert manifest["tiles"]["url_template"].startswith("placeholder://")
    assert manifest["provenance"]["fixture_digest"] == FIXTURE_DIGEST
    assert_receipt(manifest["response_receipt"], response_kind="gaia-tile-manifest")


def test_gaia_layer_catalog_unknown_layer_returns_404(tmp_path: Path) -> None:
    client = make_gaia_catalog_client(tmp_path)

    missing_layer = client.get("/gaia/layers/unknown-layer")
    missing_tile_manifest = client.get("/gaia/tile-manifests/unknown-layer")

    assert missing_layer.status_code == 404
    assert missing_tile_manifest.status_code == 404


def test_gaia_layer_catalog_does_not_break_health_or_readiness(tmp_path: Path) -> None:
    client = make_gaia_catalog_client(tmp_path)

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
