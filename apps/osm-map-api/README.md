# OSM Map API

Status: v0 production-grade scaffold

## Purpose

`osm-map-api` is the read-only Prophet Platform service surface for OpenStreetMap-derived GAIA features, map layers, advisory route graphs, Sherlock discovery records, runtime-boundary state, and SocioSphere governance state.

This is not a production tile server. It is a strict API boundary that can run against mounted fixture roots first, then later switch to service/runtime-backed stores without changing the public contract.

## Production rules

1. Preserve OSM identity and attribution.
2. Never claim safety-critical routing from OSM-only topology.
3. Serve only read-only responses in this slice.
4. Expose health and readiness separately.
5. Fail readiness if required fixture roots are absent.
6. Preserve provenance/source refs in every response.
7. Keep Lattice runtime assets gated until executable runtime admission is approved.

## Runtime configuration

Required environment variables:

- `GAIA_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/gaia-world-model`.
- `SHERLOCK_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/sherlock-search`.
- `SOCIOSPHERE_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/sociosphere`.

Optional:

- `OSM_MAP_API_HOST` — default `127.0.0.1`.
- `OSM_MAP_API_PORT` — default `8088`.

## Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /map-layers`
- `GET /map-layers/{layer_id}`
- `GET /features/by-osm/{osm_type}/{osm_id}`
- `GET /features/by-h3/{h3_cell}`
- `GET /route-graphs/osm`
- `GET /runtime-boundaries/osm`
- `GET /governance/osm`
- `GET /search/osm-demo`

## Fixture-backed contract

The first service slice reads these files from mounted repo roots:

- `gaia-world-model/fixtures/geospatial/osm-road-feature-binding.sample.v1.json`
- `gaia-world-model/fixtures/geospatial/osm-derived-map-tile-layer.sample.v1.json`
- generated output from `gaia-world-model/geospatial/osm_route_graph.py`
- `sherlock-search/examples/gaia-osm-derived-road-layer.sherlock-result.v1.json`
- `sociosphere/registry/gaia-ofif-meshlab-capability-map.v1.json`

## Safety posture

This service is read-only and advisory-only for route graph outputs until a route validation record, safety case, and operator/agency approval path exist.
