# GAIA World Model v1 Execution Plan

Status: active execution plan
Date: 2026-04-29
Scope: `SocioProphet/socioprophet`, `SocioProphet/prophet-platform`, `SocioProphet/gaia-world-model`, `SocioProphet/sherlock-search`, `SocioProphet/meshrush`, `SocioProphet/agentplane`, `SocioProphet/lattice-forge`, `SocioProphet/sociosphere`, standards repos

## Baseline position

We have completed the first serious GAIA `/map` integration slice. We have not completed the full GAIA world-model program.

The current state is:

- GAIA Workbench v0 exists as a canonical org Vue shell route under `/map` with MapLibre canvas, GAIA OSM API client/types, domain taxonomy, mocked surrounding surfaces, evidence/governance/runtime panels, fallback mode, and scoped product build.
- The fixture-backed OSM Map API is hardened for browser use and environment-specific `VITE_GAIA_MAP_API_BASE` expectations.
- The GAIA real-data adapter work is a planning contract. It does not implement live ingestion, production tile serving, runtime admission, or operational model status.

## Target architecture

```text
Raw sources
  -> Source adapters
  -> Normalized GAIA observations/features
  -> Evidence/provenance graph
  -> Storage/query layer
  -> Tile/layer services
  -> GAIA APIs
  -> Vue /map workbench
  -> Agent/governance review
  -> Runtime admission
```

GAIA is not just a map. It is a governed world-model substrate: spatial features, temporal observations, uncertainty, source rights, provenance, replay, policy, query, visualization, and agentic decision boundaries.

## Core principle

Every visible map object must become an evidence-backed, policy-governed, temporally valid, source-attributed world-model object.

That is the difference between a map viewer and GAIA.

## Workstreams

| Workstream | What remains | Integration target | Why it matters |
| --- | --- | --- | --- |
| Live OSM ingestion | Build real PBF/Overpass/diff ingestion, not fixture loading | `gaia-world-model`, `prophet-platform/apps/osm-map-api` | OSM is the base civic/transport layer for the map and world model |
| Production tiles | Generate/serve vector tiles or tile manifests from governed data | `prophet-platform`, future tile service, Vue `/map` | Browser map scale requires tiles/layer manifests, not raw feature APIs only |
| EO/satellite adapters | Add STAC/COG/Zarr/GeoTIFF adapter contracts and first fixture-backed adapter | `gaia-world-model` | Satellite/EO adds environmental observability |
| LiDAR/DEM/terrain | Add point-cloud, terrain, slope/aspect, corridor asset adapters | `gaia-world-model` | Needed for infrastructure, navigation-adjacent, and physical-world reasoning |
| Weather/reanalysis | Add forecast/reanalysis/station/radar context adapters | `gaia-world-model` | Time-varying world state requires weather and temporal validity |
| Storage/query plane | Decide and implement object store, PostGIS/GeoParquet, graph, search split | `prophet-platform`, `sherlock-search`, possibly `cloudshell-fog` | Without query/storage discipline, the data plane becomes ungovernable |
| Evidence graph | Connect layers/features/observations to source, license, digest, confidence, review state | `sherlock-search`, `meshrush`, `sociosphere` | Makes GAIA auditable, not merely visual |
| Fusion model | Combine OSM + EO + LiDAR + terrain + weather into fused indicators | `gaia-world-model`, `prophet-platform` | World modeling begins when independent signals reconcile |
| API expansion | Move from OSM Map API to GAIA World Model API | `prophet-platform` | `/map` needs layers, timelines, evidence, search, features, tiles, observations |
| UI expansion | Turn `/map` from fixture workbench into analytical workspace | `socioprophet-web/client-vue` | Product usability depends on visible evidence/governance/analysis surfaces |
| Runtime admission | Define when ingestion/fusion runtimes become Lattice-admissible | `agentplane`, `lattice-forge`, `sociosphere` | Prevents unsafe automation and premature operational claims |
| Deployment | Deploy Vue app + GAIA/OSM API + artifact storage in staging | `socioprophet`, `prophet-platform`, SourceOS repos | We need a working live demo surface, not just merged code |
| Governance | Licensing, source exposure, sensitive feeds, safety boundaries, attribution | `sociosphere`, standards repos | Real-world data has legal, ethical, and safety constraints |
| Evaluation | Contract tests, data quality gates, visual regression, API integration, replay tests | all active repos | Prevents fake progress |

## Phase 1 — Stabilize `/map` as a deployable demo

Immediate priority: deploy the existing fixture-backed `/map` and OSM API so it becomes reviewable product.

Tasks:

1. Deploy `socioprophet-web/client-vue` independently from the marketing/docs site.
2. Pick staging URLs for the Vue shell and OSM Map API.
3. Set `VITE_GAIA_MAP_API_BASE` for local, preview, staging, and production.
4. Put fixture-backed OSM Map API behind a controlled endpoint.
5. Add `/healthz`, `/readyz`, and UI status display to the staging dashboard.
6. Add browser E2E smoke tests:
   - `/map` loads;
   - Map canvas renders;
   - fallback mode renders if API unavailable;
   - live API mode renders if API available;
   - H3 lookup does not blank page;
   - evidence/governance panels render.

Repo ownership:

- `SocioProphet/socioprophet`: Vue shell deployment and E2E tests.
- `SocioProphet/prophet-platform`: OSM Map API staging config.
- `SocioProphet/sociosphere`: readiness registration.

Definition of done:

A user can open the deployed app, visit `/map`, see a real MapLibre surface, see live/fallback mode, inspect feature/evidence/governance panels, and verify backend readiness.

## Phase 2 — Implement live OSM ingestion for one bounded region

Do not start with the whole planet. Pick one bounded region.

Build:

1. OSM source adapter:
   - regional PBF or bounded Overpass extract;
   - source metadata;
   - extraction timestamp;
   - ODbL attribution;
   - source URL or replication sequence.
2. Normalization:
   - OSM node/way/relation identity;
   - tags;
   - geometry;
   - CRS;
   - bbox;
   - H3 cells;
   - GAIA entity type mapping.
3. Validation:
   - schema validation;
   - geometry validation;
   - attribution check;
   - provenance source-ref check;
   - duplicate identity check;
   - H3 coverage check.
4. Output:
   - `osm-feature-binding.v1`;
   - route graph candidate;
   - layer manifest candidate;
   - source receipt.

Definition of done:

A bounded real OSM extract produces validated GAIA feature bindings and can be served through the API to `/map`.

## Phase 3 — Production-shaped tile/layer serving

Decide and implement:

1. Tile format: vector tile manifest, MVT service, PMTiles/static artifact, or hybrid tile manifest + API metadata.
2. Tile ownership: generated by GAIA adapter pipeline, served by Prophet Platform, referenced by MapLibre.
3. Cache policy: content-addressed tile artifacts; digest-linked manifests; region/version/channel keyed.
4. Governance: attribution displayed; license refs preserved; source refs queryable; stale/expired layers marked.

Definition of done:

The `/map` UI loads at least one real generated layer from a backend/manifest and displays attribution plus evidence metadata.

## Phase 4 — EO/satellite adapter family

Start with disciplined EO context ingestion, not AI fusion.

First adapter candidates:

1. NDVI or vegetation index.
2. Land-surface temperature.
3. Soil moisture.
4. Cloud/quality mask.
5. Simple temporal raster context.

Every EO observation must include source/provider/product ID, acquisition time, processing time, CRS/grid/tile ref, resolution, quality mask, uncertainty/quality flags, temporal validity, license/access constraints, and provenance refs.

Definition of done:

A fixture-backed EO observation layer loads in `/map`, joins to a spatial index, and can be inspected with provenance/quality metadata.

## Phase 5 — Terrain, LiDAR, and DEM context

Build after OSM and first EO layer.

Build:

1. DEM adapter: elevation, slope, aspect, roughness, hydrology context later.
2. LiDAR adapter: COPC/LAZ source envelope, point-cloud metadata, vertical datum, classification codes, confidence/quality, derived corridor/infrastructure features.
3. Safety case: advisory-only, no navigation authority, no infrastructure action without approval, rollback/demotion plan.

Definition of done:

A LiDAR/terrain fixture validates and appears as evidence/context in `/map`, with explicit advisory boundary.

## Phase 6 — Weather/reanalysis time dimension

Build:

1. Weather/reanalysis context record: issue time, valid time, forecast horizon, variables/units, grid/resolution, uncertainty/quality, source refs.
2. UI: timeline slider, valid-time display, stale data warning.
3. API: query by bbox/H3/time, return latest valid observation, return history for selected feature/layer.

Definition of done:

The map can show a time-scoped environmental layer and clearly indicate valid time and uncertainty.

## Phase 7 — Fusion semantics

Fusion is governed reconciliation of heterogeneous evidence, not overlaying layers.

Fusion model includes:

- inputs: OSM, EO, LiDAR/terrain, weather/reanalysis, human/agent annotations later;
- common keys: H3/S2, geometry, feature ID, temporal window, source authority, confidence;
- outputs: fused feature, fused indicator, conflict record, uncertainty envelope, evidence chain;
- discipline: never erase uncertainty, never collapse model output into observation, always preserve temporal validity, always expose source conflict.

Definition of done:

One fused indicator exists for a bounded region using at least two source families, with uncertainty and evidence refs preserved.

## Phase 8 — GAIA World Model API

Evolve from OSM Map API to GAIA World Model API.

API groups:

- Catalog: `/layers`, `/layers/{id}`, `/sources`, `/schemas`.
- Features: `/features/by-osm/{type}/{id}`, `/features/by-h3/{cell}`, `/features/by-bbox`, `/features/{gaia_id}`.
- Observations: `/observations/by-h3/{cell}`, `/observations/by-feature/{id}`, `/observations/by-time`.
- Evidence: `/evidence/{id}`, `/provenance/{id}`, `/receipts/{id}`.
- Tiles: `/tiles/{layer}/{z}/{x}/{y}`, `/tile-manifests/{layer}`.
- Governance: `/governance/layers/{id}`, `/runtime-boundaries`, `/safety-status`.
- Search: `/search`, `/search/osm`, `/search/evidence`, `/search/spatial`.

Definition of done:

API surface is OpenAPI-described, tested, and consumed by Vue client with generated or checked TypeScript types.

## Phase 9 — Vue `/map` analytical workspace

UI backlog:

1. Layer catalog drawer.
2. Timeline/valid-time control.
3. H3/bbox query mode.
4. Feature selection and pinning.
5. Evidence panel.
6. Governance panel.
7. Source/license panel.
8. Runtime-boundary panel.
9. Uncertainty visualization.
10. Sherlock search integration.
11. Agent review handoff.
12. Export/share evidence bundle.
13. Fallback/live/stale status indicator.
14. Visual parity pass against old React shell.

Definition of done:

A user can inspect a region, toggle layers, inspect a feature, view evidence/provenance/freshness/uncertainty, and request agent review.

## Phase 10 — Runtime admission and safety governance

Admission requirements:

1. Executable entrypoint.
2. Validation command.
3. Passing fixtures.
4. Source exposure review.
5. License/attribution review.
6. Failure-mode document.
7. Rollback/demotion semantics.
8. Evidence output definition.
9. Human approval boundary.
10. Runtime monitoring plan.

Definition of done:

One non-dangerous runtime, probably OSM bounded ingest, is admitted as a reviewed runtime with evidence and rollback semantics.

## Phase 11 — Deployment and operations

Minimum staging topology:

1. Vue app shell deployed separately from marketing/docs.
2. GAIA/OSM API fixture mode and bounded live OSM mode with readiness checks.
3. Storage: object store, structured feature indexes, evidence search index, tile cache.
4. CI/CD: product build, API tests, OpenAPI contract, fixture validation, E2E smoke.
5. Observability: API health, ingestion job status, layer freshness, failed validation records, user-visible data mode.

Definition of done:

A staging URL exists and demonstrates bounded real OSM region with evidence/provenance.

## Recommended execution order

1. Deploy current fixture-backed `/map` and OSM API in staging.
2. Add real bounded OSM ingestion.
3. Add tile/layer manifest serving.
4. Add layer catalog UI.
5. Add Sherlock-backed search/evidence API.
6. Add first EO/satellite fixture adapter.
7. Add temporal query model.
8. Add fusion schema and one fused indicator.
9. Add runtime admission for OSM ingest.
10. Add visual review and demo polish.

## Agent/Codex work packages

### `SocioProphet/gaia-world-model`

- Implement bounded OSM source adapter fixture and validator.
- Add EO observation schema and sample NDVI/STAC-style fixture.
- Add terrain/DEM context schema and fixture.
- Add weather/reanalysis temporal context schema.
- Add fusion output schema with uncertainty and evidence refs.

### `SocioProphet/prophet-platform`

- Add GAIA layer catalog API.
- Add bounded OSM ingest/import endpoint or job runner.
- Add tile manifest endpoint.
- Add observation query endpoints by H3/bbox/time.
- Add evidence/provenance API proxy.

### `SocioProphet/socioprophet`

- Add layer catalog drawer to `/map`.
- Add timeline control.
- Add feature/evidence/governance panel split.
- Add Sherlock search box.
- Add visual parity pass against old React shell.

### `SocioProphet/sherlock-search`

- Index GAIA layer/feature/evidence records.
- Add spatial evidence search fixture.
- Add temporal evidence result fixture.

### `SocioProphet/meshrush`

- Add fused-feature graph-view fixture.
- Add contested-evidence graph-view fixture.

### `SocioProphet/agentplane`

- Add runtime admission review candidate for OSM ingest.
- Add approval-required review candidate for safety-adjacent fusion.

### `SocioProphet/sociosphere`

- Update GAIA readiness registry with live-ingest lanes.
- Add validation lane registry for EO, terrain, weather, fusion.

## Current estimates

- GAIA `/map` fixture-backed product slice: 95%.
- Full GAIA world-model program: 40%.
- Live OSM ingestion: 0–10%.
- Production tile/layer serving: 0–15%.
- EO/satellite integration: planning/fixture level.
- LiDAR/terrain integration: planning/fixture level.
- Weather/reanalysis integration: planning.
- Fusion model: not production implemented.
- Runtime admission: not production implemented.
- Deployment: not complete.

## Next milestone target

A staged GAIA v1 demo should include:

```text
/map deployed + bounded live OSM + tile layer + evidence search + governance panel + first runtime admission candidate
```

That moves the full GAIA program from roughly 40% toward 60–65% and makes it credible as a live platform rather than only a proof slice.
