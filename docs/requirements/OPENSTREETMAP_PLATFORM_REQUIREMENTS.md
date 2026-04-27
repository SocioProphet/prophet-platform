# OpenStreetMap Platform Requirements

Status: v0 platform requirements
Date: 2026-04-27
Owner surface: prophet-platform

## Purpose

OpenStreetMap is the first open geospatial base-map and routable-topology substrate for the GAIA / OFIF / Sherlock / Lattice / MeshLab / Control Tower program.

OSM is not the whole digital twin. OSM supplies open, editable, community-governed map topology and feature semantics. GAIA extends OSM with evidence, ontology, field events, remote sensing, LiDAR/HD-map features, simulation, decision cards, and provenance.

## Doctrine

```text
OSM base geography
  -> GAIA spatial/entity binding
  -> OFIF field observations and evidence
  -> GAIA world-state features and map layers
  -> Sherlock discovery records
  -> Lattice runtime provenance when processing is executable
  -> SocioSphere governance and validation gates
```

## Required platform capabilities

### 1. OSM ingestion

The platform must support ingestion of OSM extracts or services as source data.

Required source forms:

- PBF extracts;
- Overpass-style query results;
- planet/region extracts;
- incremental diffs where available;
- local extracts sampled by Lampstand;
- curated internal correction layers without mutating original OSM source.

### 2. OSM feature identity preservation

GAIA must preserve original OSM identity fields when binding features:

- OSM node ID;
- OSM way ID;
- OSM relation ID;
- tags;
- version/timestamp where available;
- source extract ID;
- license/source attribution metadata.

Derived GAIA features must cite OSM refs instead of overwriting them.

### 3. Spatial indexing

OSM features must be bindable to:

- WGS84 geometry;
- H3 cells as first shared operational index;
- bounding boxes;
- route/corridor refs;
- administrative areas;
- optional future S2/DGGS cells.

### 4. Routing topology

OSM must support routable graph construction for:

- roads;
- pedestrian paths;
- bicycle routing;
- service/access restrictions;
- rail corridors where OSM data is sufficiently modeled;
- multimodal transfer context when combined with GTFS/NeTEx.

The platform should not hardcode one routing engine as canonical. Candidate adapters:

- Valhalla;
- OSRM;
- GraphHopper;
- OpenTripPlanner;
- pgRouting;
- custom GAIA route graph contracts.

### 5. Map tile serving

The platform must support open map rendering paths:

- vector tiles from OSM-derived features;
- raster tiles where required;
- MapLibre-compatible style/layer manifests;
- optional Cesium/3D Tiles path for globe/terrain/3D city context;
- attribution-preserving map surface metadata.

### 6. OSM + remote sensing + LiDAR fusion

OSM must be treated as a base semantic/topology layer that can be fused with:

- satellite/reanalysis context;
- LiDAR point clouds;
- HD map features;
- field observations from OFIF;
- local files sampled by Lampstand;
- control-tower asset and route-risk records.

OSM is not sufficient for HD navigation or safety-critical claims. LiDAR/HD-map evidence and validation records are required for those cases.

### 7. Attribution and licensing

The platform must preserve OSM attribution and licensing metadata.

Derived products must carry source/attribution refs so UI, reports, and publication artifacts can satisfy attribution requirements.

### 8. Governance and validation

SocioSphere must track OSM integration as a governed platform capability.

Required validation gates:

- OSM source refs preserved;
- OSM-derived feature IDs do not collide with GAIA canonical IDs;
- derived features cite source OSM refs;
- tile/style manifests include attribution metadata;
- routing outputs disclose whether they are advisory, validated, or not-for-navigation;
- safety-critical route claims require validation beyond raw OSM topology.

## Repository responsibilities

| Repository | Responsibility |
| --- | --- |
| `prophet-platform` | platform-level requirements, product/control-surface requirements, progress tracking |
| `gaia-world-model` | OSM bindings, spatial/entity semantics, map layers, route graph contracts |
| `sherlock-search` | discovery records for OSM-derived features, routes, tiles, decision cards |
| `lampstand` | local OSM extract/file sampling and percolation |
| `lattice-forge` | reproducible runtimes for OSM ingestion/tile/routing only after runtime boundary is defined |
| `sociosphere` | governance, attribution, source-exposure, validation lanes |
| `orion-field-intelligence` | field events tied to OSM/GAIA features |

## Required GAIA artifacts

- `docs/integrations/OPENSTREETMAP_INTEGRATION.md`
- `schemas/geospatial/osm_feature_binding.v1.schema.json`
- `schemas/geospatial/map_tile_layer_manifest.v1.schema.json`
- `fixtures/geospatial/osm-road-feature-binding.sample.v1.json`
- `fixtures/search/osm-derived-route-layer.sherlock-record.sample.v1.json`

## Required SocioSphere artifacts

- OSM validation lane in GAIA / OFIF / MeshLab capability map;
- OSM source-attribution governance rule;
- change propagation rule for OSM integration schema/fixture changes.

## Non-goals

- Do not treat OSM as the whole world model.
- Do not mutate original OSM identity or tags in derived GAIA records.
- Do not make OSM-only topology sufficient for HD/safety-critical navigation.
- Do not hide OSM attribution in generated tiles, reports, or decision cards.
- Do not hardcode one router as the canonical system of record.

## First implementation target

The first implementation slice should prove:

```text
OSM road/rail/path feature binding
  -> GAIA spatial feature with H3 refs
  -> MapLibre-compatible layer manifest
  -> Sherlock searchable record
  -> SocioSphere validation lane
```
