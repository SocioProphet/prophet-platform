"""Read-only repository for fixture-backed OSM API artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import Settings


class ArtifactError(RuntimeError):
    """Raised when required fixture artifacts are invalid or unavailable."""


@dataclass(frozen=True)
class OSMArtifactRepository:
    """Read validated static artifacts from mounted repository roots."""

    settings: Settings

    @property
    def osm_feature_binding_path(self) -> Path:
        return self.settings.gaia_fixture_root / "fixtures/geospatial/osm-road-feature-binding.sample.v1.json"

    @property
    def osm_tile_layer_path(self) -> Path:
        return self.settings.gaia_fixture_root / "fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json"

    @property
    def osm_route_graph_path(self) -> Path:
        return self.settings.gaia_fixture_root / "fixtures/geospatial/osm-route-graph.sample.v1.json"

    @property
    def sherlock_osm_result_path(self) -> Path:
        return self.settings.sherlock_fixture_root / "examples/gaia-osm-derived-road-layer.sherlock-result.v1.json"

    @property
    def sociosphere_capability_map_path(self) -> Path:
        return (
            self.settings.sociosphere_fixture_root
            / "registry/gaia-ofif-meshlab-capability-map.v1.json"
        )

    @property
    def gaia_layer_manifest_candidate_path(self) -> Path:
        root = self.settings.gaia_layer_catalog_root or Path(__file__).resolve().parents[1]
        return root / "fixtures/geospatial/osm-layer-manifest-candidate.v1.json"

    def readiness_errors(self) -> list[str]:
        errors = list(self.settings.missing_roots())
        for path in [
            self.osm_feature_binding_path,
            self.osm_tile_layer_path,
            self.osm_route_graph_path,
            self.sherlock_osm_result_path,
            self.sociosphere_capability_map_path,
            self.gaia_layer_manifest_candidate_path,
        ]:
            if not path.exists():
                errors.append(f"missing artifact: {path}")
        if not errors:
            try:
                self._assert_attribution(self.osm_tile_layer())
                self._assert_attribution(self.osm_feature_binding())
                self._assert_advisory_route(self.osm_route_graph())
            except ArtifactError as exc:
                errors.append(str(exc))
        return errors

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except FileNotFoundError as exc:
            raise ArtifactError(f"artifact not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ArtifactError(f"invalid JSON artifact {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ArtifactError(f"artifact top level must be object: {path}")
        return value

    def _assert_attribution(self, artifact: dict[str, Any]) -> None:
        attribution = artifact.get("attribution")
        if not isinstance(attribution, dict):
            raise ArtifactError("artifact missing attribution object")
        text = attribution.get("attribution_text")
        license_ref = attribution.get("license_ref") or attribution.get("license_refs")
        if not text:
            raise ArtifactError("artifact attribution_text is required")
        if not license_ref:
            raise ArtifactError("artifact license attribution is required")

    def _assert_advisory_route(self, route_graph: dict[str, Any]) -> None:
        if route_graph.get("safety_status") != "advisory":
            raise ArtifactError("OSM route graph must be advisory in fixture mode")

    @staticmethod
    def _is_osm_validation_lane(lane: dict[str, Any]) -> bool:
        lane_id = str(lane.get("id", "")).lower()
        lane_role = str(lane.get("role", "")).lower()
        return (
            "osm" in lane_id
            or "openstreetmap" in lane_id
            or "open-street-map" in lane_id
            or "openstreetmap" in lane_role
            or "open-street-map" in lane_role
        )

    def osm_feature_binding(self) -> dict[str, Any]:
        artifact = self._load_json(self.osm_feature_binding_path)
        self._assert_attribution(artifact)
        return artifact

    def osm_tile_layer(self) -> dict[str, Any]:
        artifact = self._load_json(self.osm_tile_layer_path)
        self._assert_attribution(artifact)
        return artifact

    def osm_route_graph(self) -> dict[str, Any]:
        artifact = self._load_json(self.osm_route_graph_path)
        self._assert_attribution(artifact)
        self._assert_advisory_route(artifact)
        return artifact

    def sherlock_osm_result(self) -> dict[str, Any]:
        return self._load_json(self.sherlock_osm_result_path)

    def sociosphere_capability_map(self) -> dict[str, Any]:
        return self._load_json(self.sociosphere_capability_map_path)

    def map_layers(self) -> list[dict[str, Any]]:
        return [self.osm_tile_layer()]

    def map_layer(self, layer_id: str) -> dict[str, Any] | None:
        layer = self.osm_tile_layer()
        if layer.get("layer_id") == layer_id:
            return layer
        return None

    def feature_by_osm(self, osm_type: str, osm_id: str) -> dict[str, Any] | None:
        feature = self.osm_feature_binding()
        osm_ref = feature.get("osm_ref", {})
        if osm_ref.get("osm_type") == osm_type and str(osm_ref.get("osm_id")) == str(osm_id):
            return feature
        return None

    def features_by_h3(self, h3_cell: str) -> dict[str, Any]:
        feature = self.osm_feature_binding()
        layer = self.osm_tile_layer()
        feature_cells = feature.get("spatial", {}).get("h3_cells", [])
        layer_cells = layer.get("spatial", {}).get("h3_cells", [])
        return {
            "h3_cell": h3_cell,
            "features": [feature] if h3_cell in feature_cells else [],
            "layers": [layer] if h3_cell in layer_cells else [],
        }

    def runtime_boundaries_osm(self) -> dict[str, Any]:
        return {
            "runtimes": [
                {
                    "name": "gaia-osm-ingestion-runtime",
                    "status": "executable-proof",
                    "validation_command": "python3 geospatial/osm_ingest.py fixtures/geospatial/osm-way-input.sample.v1.json /tmp/osm-feature-bindings.json",
                    "lattice_admission": "not-admitted",
                },
                {
                    "name": "gaia-osm-route-graph-runtime",
                    "status": "executable-proof",
                    "validation_command": "python3 geospatial/osm_route_graph.py fixtures/geospatial/osm-road-feature-binding.sample.v1.json /tmp/osm-route-graph.json",
                    "lattice_admission": "not-admitted",
                },
                {
                    "name": "gaia-osm-tile-export-runtime",
                    "status": "executable-proof",
                    "validation_command": "python3 geospatial/osm_tile_export.py fixtures/geospatial/osm-road-feature-binding.sample.v1.json /tmp/osm-derived-map-tile-layer.json",
                    "lattice_admission": "not-admitted",
                },
            ],
            "admission_rule": "No Lattice RuntimeAsset before reviewed boundary, executable entrypoint, validation command, passing fixture, policy constraints, rollback semantics, and named evidence outputs.",
        }

    def governance_osm(self) -> dict[str, Any]:
        capability_map = self.sociosphere_capability_map()
        lanes = capability_map.get("validation_lanes", [])
        osm_lanes = [
            lane for lane in lanes if isinstance(lane, dict) and self._is_osm_validation_lane(lane)
        ]
        return {
            "validation_lanes": osm_lanes,
            "source": "SocioProphet/sociosphere:registry/gaia-ofif-meshlab-capability-map.v1.json",
            "attribution_required": True,
            "unresolved_blockers": [],
        }

    def gaia_layer_manifest_candidate(self) -> dict[str, Any]:
        artifact = self._load_json(self.gaia_layer_manifest_candidate_path)
        self._assert_attribution(artifact)
        return artifact

    def gaia_layers(self) -> list[dict[str, Any]]:
        """Return all GAIA layer catalog entries (fixture-backed)."""
        return [self.gaia_layer_manifest_candidate()]

    def gaia_layer(self, layer_id: str) -> dict[str, Any] | None:
        """Return a specific GAIA layer by ID, or None if not found."""
        manifest = self.gaia_layer_manifest_candidate()
        if manifest.get("layer_id") == layer_id:
            return manifest
        return None

    def gaia_tile_manifest(self, layer_id: str) -> dict[str, Any] | None:
        """Return the tile manifest for a GAIA layer by ID, or None if not found."""
        manifest = self.gaia_layer_manifest_candidate()
        if manifest.get("layer_id") != layer_id:
            return None
        tiles = manifest.get("tiles", {})
        return {
            "layer_id": layer_id,
            "tiles": tiles,
            "spatial": manifest.get("spatial", {}),
            "attribution": manifest.get("attribution", {}),
            "production_tile_serving": manifest.get("production_tile_serving", False),
            "tile_serving_note": manifest.get(
                "tile_serving_note",
                "Fixture-backed placeholder. Not production tile serving.",
            ),
            "provenance": manifest.get("provenance", {}),
            "classification": manifest.get("classification", {}),
            "status": manifest.get("status", {}),
        }
