# OSM Control Surface Requirements

Status: v0 product/control-surface requirements
Date: 2026-04-27
Owner surface: prophet-platform

## Purpose

Define the Prophet Platform UI/API control-surface requirements for OpenStreetMap-backed map, tile, route, and feature inspection workflows.

This document complements:

- `docs/requirements/OPENSTREETMAP_PLATFORM_REQUIREMENTS.md`
- `docs/acceptance/OPENSTREETMAP_MAP_ROUTING_ACCEPTANCE.md`

## Required views

### 1. Map layer catalog

The platform must expose a map layer catalog view showing:

- layer title;
- layer ID;
- layer type;
- source systems;
- source refs;
- attribution text;
- license refs;
- provenance refs;
- safety/advisory status;
- last generated/updated time.

Minimum accepted fixture:

- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json`

### 2. Attribution display

Every OSM-derived layer must show attribution in the UI.

Required behavior:

- display attribution text when the layer is visible;
- expose source URLs/license refs in layer details;
- preserve attribution in exported reports or decision cards.

Reject if attribution is hidden or omitted.

### 3. Feature inspector

The platform must expose a feature inspector for OSM-derived GAIA features.

Required fields:

- GAIA entity ID;
- GAIA entity type;
- OSM type;
- OSM ID;
- OSM tags;
- source extract ref;
- H3 cells;
- geometry ref;
- routing/advisory status;
- attribution;
- provenance.

Minimum accepted fixture:

- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-road-feature-binding.sample.v1.json`

### 4. Spatial/H3 search

The platform must allow filtering OSM-derived artifacts by:

- H3 cell;
- OSM ID;
- GAIA entity ID;
- layer ID;
- source extract ref;
- route/corridor ref when available.

This may initially be backed by Sherlock discovery records.

Minimum accepted fixture:

- `SocioProphet/sherlock-search:examples/gaia-osm-derived-road-layer.sherlock-result.v1.json`

### 5. Route status display

Any OSM-derived route or route-layer output must show a route safety/advisory status.

Allowed statuses:

- advisory;
- validated;
- restricted;
- not-for-navigation;
- unknown.

Default for OSM-only outputs: `advisory`.

Safety-critical status requires additional evidence and validation.

### 6. Runtime boundary status

The platform must disclose whether an OSM-related runtime is:

- planning reference only;
- boundary-defined;
- executable proof;
- Lattice admission-ready;
- packaged as Lattice RuntimeAsset.

Current state:

- `gaia-osm-ingestion-runtime`: executable proof in GAIA, not automatically admitted to Lattice Forge.
- `gaia-osm-route-graph-runtime`: boundary-defined only.
- `gaia-osm-tile-export-runtime`: boundary-defined only.

### 7. Governance status

The platform must expose governance status for OSM integration:

- SocioSphere validation lane present;
- change-propagation rule present;
- attribution/source-exposure review state;
- unresolved blockers.

## Minimal demo flow

The first UI/control-surface demo should support:

```text
Open OSM layer catalog
  -> select GAIA OSM Demo Road Layer
  -> display attribution
  -> inspect OSM way 424242
  -> show GAIA entity binding
  -> show H3 cells
  -> show advisory route status
  -> open Sherlock discovery record
```

## API surface requirements

Initial API endpoints may be local/static, but must be shaped for future service use:

- `GET /map-layers`
- `GET /map-layers/{layer_id}`
- `GET /features/{gaia_entity_id}`
- `GET /features/by-osm/{osm_type}/{osm_id}`
- `GET /features/by-h3/{h3_cell}`
- `GET /runtime-boundaries/osm`
- `GET /governance/osm`

## Non-goals

- Do not require a live OSM tile server for the first fixture-backed demo.
- Do not claim safety-critical routing from OSM-only topology.
- Do not admit OSM runtimes to Lattice without executable boundary and validation.
- Do not create a proprietary map data lock-in path.

## Acceptance summary

The OSM control surface is minimally acceptable when it can display fixture-backed layer, feature, attribution, H3, advisory route status, Sherlock discovery, runtime-boundary, and governance state.
