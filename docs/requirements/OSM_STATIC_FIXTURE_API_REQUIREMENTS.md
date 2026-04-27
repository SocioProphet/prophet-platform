# OSM Static Fixture API / Demo Requirements

Status: v0 product/API requirements
Date: 2026-04-27
Owner surface: prophet-platform

## Purpose

Define the first static fixture-backed API/demo surface for OpenStreetMap integration in Prophet Platform.

This is not a production map server. It is the minimum useful product surface for proving OSM-derived GAIA bindings, MapLibre layer manifests, advisory route graph outputs, Sherlock discovery records, runtime boundary state, and SocioSphere governance state.

## Demo doctrine

```text
Static fixtures first
  -> local API surface
  -> UI feature inspection and map layer catalog
  -> runtime/governance state visible
  -> later replace static fixture source with service/runtime-backed adapters
```

## Required static fixture inputs

The demo API must be able to read or project from these fixtures:

- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-way-input.sample.v1.json`
- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-road-feature-binding.sample.v1.json`
- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json`
- generated output from `geospatial/osm_ingest.py`
- generated output from `geospatial/osm_tile_export.py`
- generated output from `geospatial/osm_route_graph.py`
- `SocioProphet/sherlock-search:examples/gaia-osm-derived-road-layer.sherlock-result.v1.json`
- `SocioProphet/sociosphere:registry/gaia-ofif-meshlab-capability-map.v1.json`

## Required endpoints

### `GET /map-layers`

Returns a list of available map layers.

Required fields per layer:

- `layer_id`
- `title`
- `layer_type`
- `attribution.attribution_text`
- `tiles.url_template`
- `provenance.source_refs`
- `classification.handling_tags`

Initial source:

- `osm-derived-map-tile-layer.sample.v1.json`

### `GET /map-layers/{layer_id}`

Returns a full `MapTileLayerManifest`.

Required behavior:

- include attribution text;
- include source refs;
- expose tile URL template;
- expose H3 and bbox spatial refs where present.

### `GET /features/by-osm/{osm_type}/{osm_id}`

Returns the matching `OSMFeatureBinding`.

Required behavior:

- preserve OSM type and ID;
- include OSM tags;
- include GAIA entity ref;
- include attribution;
- include routing safety/advisory status.

Initial accepted fixture path:

- `osm-road-feature-binding.sample.v1.json`

### `GET /features/by-h3/{h3_cell}`

Returns OSM-derived GAIA feature bindings and layers covering the H3 cell.

Required behavior:

- match against `spatial.h3_cells`;
- include feature refs and layer refs;
- include advisory/safety status.

### `GET /route-graphs/osm`

Returns OSM-derived advisory route graph manifests.

Required behavior:

- return generated route graph output from `geospatial/osm_route_graph.py` when available;
- mark route graph `safety_status=advisory` by default;
- include OSM attribution and provenance refs.

### `GET /runtime-boundaries/osm`

Returns OSM runtime boundary state.

Required fields:

- `gaia-osm-ingestion-runtime`
- `gaia-osm-route-graph-runtime`
- `gaia-osm-tile-export-runtime`
- current status: boundary-defined, executable-proof, Lattice-admission-ready, or packaged;
- validation command refs;
- admission blockers.

### `GET /governance/osm`

Returns governance state for OSM integration.

Required fields:

- SocioSphere OSM validation lane;
- OSM change-propagation rule;
- attribution/source-exposure state;
- unresolved blockers.

### `GET /search/osm-demo`

Returns the Sherlock OSM-derived discovery record.

Required behavior:

- include `entity_type=MAP_LAYER`;
- include H3 and OSM spatial refs;
- include evidence refs;
- include provenance refs;
- expose `open_map=true` action.

## UI demo acceptance

A minimal UI/demo is acceptable if it can:

1. Show a map layer catalog.
2. Select `GAIA OSM Demo Road Layer`.
3. Display OSM attribution while selected.
4. Inspect OSM way `424242`.
5. Show the GAIA entity binding.
6. Show H3 cells.
7. Show route graph advisory status.
8. Show runtime boundary status for OSM ingestion/tile/route runtimes.
9. Show SocioSphere governance state.
10. Open or display the Sherlock discovery record.

## Static-to-runtime migration path

The initial API may read fixture files directly.

Migration sequence:

1. Static fixture API.
2. Local generated outputs from GAIA scripts.
3. Runtime-backed outputs from Lattice-admitted runtime assets.
4. Service-backed ingestion/tile/routing adapters.
5. Federated discovery through Sherlock and governed deployment through SocioSphere.

## Non-goals

- Do not require a production tile server for the first demo.
- Do not claim safety-critical routing.
- Do not bypass attribution display.
- Do not admit runtimes to Lattice Forge before admission criteria are satisfied.
- Do not build a proprietary OSM fork or mutate source OSM identities.

## First implementation target

A small route in Prophet Platform can serve static JSON from checked-out fixture paths or a generated fixture bundle.

The first target is read-only and non-mutating.
