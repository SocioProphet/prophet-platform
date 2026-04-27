# OpenStreetMap Map / Tile / Routing Acceptance Criteria

Status: v0 product acceptance criteria
Date: 2026-04-27
Owner surface: prophet-platform

## Purpose

This document defines acceptance criteria for OpenStreetMap-backed map, tile, route, and discovery surfaces in Prophet Platform.

OSM is the first open base-map and routable-topology substrate. Prophet Platform must treat OSM as a governed source layer, not as the whole world model.

## Acceptance scope

The first OSM product slice is accepted when the platform can demonstrate:

```text
OSM feature binding
  -> GAIA spatial feature
  -> MapLibre-compatible tile/layer manifest
  -> Sherlock searchable map-layer record
  -> SocioSphere validation lane
```

## A. Source and attribution acceptance

A1. OSM-derived features preserve OSM source identity:

- node ID where applicable;
- way ID where applicable;
- relation ID where applicable;
- source tags;
- extract/source ref;
- version/timestamp where available.

A2. OSM attribution is present in every generated user-facing map/tile/report layer.

A3. Generated outputs include license/source refs such as ODbL or equivalent source metadata.

A4. Derived GAIA features cite original OSM refs and do not overwrite or mutate source OSM identity.

## B. GAIA binding acceptance

B1. A valid `OSMFeatureBinding` exists for at least one demo OSM feature.

B2. The binding includes:

- OSM ref;
- GAIA entity ref;
- geometry ref;
- H3 refs;
- attribution;
- provenance;
- classification/handling tags.

B3. GAIA feature IDs are distinct from OSM IDs.

B4. OSM-derived bindings pass GAIA contract fixture validation.

## C. Map / tile acceptance

C1. A valid `MapTileLayerManifest` exists for an OSM-derived layer.

C2. The manifest includes:

- layer ID;
- layer type;
- tile URL template;
- min/max zoom;
- source refs;
- attribution text;
- license refs;
- provenance refs.

C3. The manifest is MapLibre-compatible or explicitly identifies the adapter needed for MapLibre rendering.

C4. The UI/control surface must display attribution text with the layer.

C5. Raster or vector tile rendering does not create safety-critical route assertions.

## D. Routing acceptance

D1. OSM-derived route graph outputs are marked `advisory` unless validated by additional evidence.

D2. Safety-critical or HD navigation claims require extra validation, such as:

- LiDAR / HD map evidence;
- field observations;
- route validation record;
- clearance validation record;
- operator/agency approval where applicable.

D3. Route output must disclose:

- source data refs;
- routing engine or runtime ref when executable;
- safety status;
- attribution refs;
- date/time of source extract or query.

D4. The platform must not hardcode one router as canonical. Route engines are adapters, not the system of record.

## E. Sherlock discovery acceptance

E1. OSM-derived map/tile/route artifacts emit Sherlock search records.

E2. Search records include:

- `source=GAIA`;
- `entity_type=MAP_LAYER` or relevant future route entity;
- OSM spatial refs;
- H3 refs;
- evidence refs;
- provenance refs;
- attribution-preserving handling tags.

E3. Search results should support queries such as:

- "OSM road layer demo";
- "features in H3 cell 8928308280fffff";
- "OSM way 424242";
- "MapLibre road layer".

## F. SocioSphere governance acceptance

F1. SocioSphere capability map includes an OSM validation lane.

F2. SocioSphere change propagation rules include OSM schema/fixture changes.

F3. Source-exposure and attribution checks are identified before public release.

F4. OSM runtime assets are blocked from Lattice Forge until runtime admission criteria are met.

## G. Lattice runtime admission acceptance

A Lattice RuntimeAsset for OSM ingestion, routing, or tile export may be added only after:

- executable entrypoint exists;
- validation command exists;
- source/attribution preservation is tested;
- generated fixture passes validation;
- rollback semantics are explicit;
- network posture is declared.

Initial runtime boundaries are tracked in:

`SocioProphet/gaia-world-model:docs/integrations/RUNTIME_BOUNDARY_DEFINITIONS.md`

## H. Non-acceptance / rejection criteria

Reject the slice if:

- OSM attribution is missing;
- OSM identity is overwritten by GAIA IDs without source refs;
- route output claims safety-critical validity from OSM alone;
- generated tile layer lacks provenance;
- runtime asset is added to Lattice before executable boundary exists;
- Sherlock record cannot link back to OSM and GAIA source refs.

## Current fixture targets

- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-road-feature-binding.sample.v1.json`
- `SocioProphet/gaia-world-model:fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json`
- `SocioProphet/sherlock-search:examples/gaia-osm-derived-road-layer.sherlock-result.v1.json`
