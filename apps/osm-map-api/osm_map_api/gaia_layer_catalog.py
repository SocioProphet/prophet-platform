"""Fixture-backed GAIA layer catalog helpers.

This module exposes bounded OSM ingest layer metadata without implementing
production tile serving or live OSM ingestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .repository import ArtifactError, OSMArtifactRepository

BOUNDED_OSM_MANIFEST_PATH = "examples/osm-bounded-ingest/osm-layer-manifest-candidate.v1.json"


def _manifest_path(repo: OSMArtifactRepository) -> Path:
    return repo.settings.gaia_fixture_root / BOUNDED_OSM_MANIFEST_PATH


def _assert_layer_manifest(layer: dict[str, Any]) -> None:
    if not layer.get("layer_id"):
        raise ArtifactError("GAIA layer manifest missing layer_id")
    attribution = layer.get("attribution")
    if not isinstance(attribution, dict):
        raise ArtifactError("GAIA layer manifest missing attribution")
    if not attribution.get("attribution_text"):
        raise ArtifactError("GAIA layer manifest missing attribution_text")
    if not attribution.get("license_refs"):
        raise ArtifactError("GAIA layer manifest missing license_refs")
    provenance = layer.get("provenance")
    if not isinstance(provenance, dict):
        raise ArtifactError("GAIA layer manifest missing provenance")
    if not provenance.get("fixture_digest"):
        raise ArtifactError("GAIA layer manifest missing fixture_digest")
    if not provenance.get("source_refs"):
        raise ArtifactError("GAIA layer manifest missing source_refs")
    spatial = layer.get("spatial")
    if not isinstance(spatial, dict) or not spatial.get("bbox") or not spatial.get("h3_cells"):
        raise ArtifactError("GAIA layer manifest missing bbox or h3_cells")
    tiles = layer.get("tiles")
    if not isinstance(tiles, dict):
        raise ArtifactError("GAIA layer manifest missing tiles")
    url_template = str(tiles.get("url_template", ""))
    if not url_template.startswith("placeholder://"):
        raise ArtifactError("GAIA layer manifest must use placeholder tile URL in fixture mode")
    description = str(layer.get("description", "")).lower()
    if "not production" not in description and "non-production" not in description:
        raise ArtifactError("GAIA layer manifest must declare non-production tile boundary")


def load_bounded_osm_layer(repo: OSMArtifactRepository) -> dict[str, Any]:
    layer = repo._load_json(_manifest_path(repo))
    _assert_layer_manifest(layer)
    return layer


def gaia_layers(repo: OSMArtifactRepository) -> list[dict[str, Any]]:
    return [load_bounded_osm_layer(repo)]


def gaia_layer(repo: OSMArtifactRepository, layer_id: str) -> dict[str, Any] | None:
    layer = load_bounded_osm_layer(repo)
    if layer.get("layer_id") == layer_id:
        return layer
    return None


def gaia_tile_manifest(repo: OSMArtifactRepository, layer_id: str) -> dict[str, Any] | None:
    layer = gaia_layer(repo, layer_id)
    if layer is None:
        return None
    return {
        "manifest_version": layer.get("manifest_version"),
        "layer_id": layer.get("layer_id"),
        "layer_type": layer.get("layer_type"),
        "title": layer.get("title"),
        "description": layer.get("description"),
        "tile_serving_status": "fixture-placeholder-not-production",
        "production_tile_serving": False,
        "tiles": layer.get("tiles"),
        "spatial": layer.get("spatial"),
        "attribution": layer.get("attribution"),
        "provenance": layer.get("provenance"),
        "classification": layer.get("classification"),
    }
