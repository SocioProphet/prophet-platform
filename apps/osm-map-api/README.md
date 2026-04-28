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
8. Permit browser access only from explicitly configured origins.

## Runtime configuration

Required environment variables:

- `GAIA_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/gaia-world-model`.
- `SHERLOCK_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/sherlock-search`.
- `SOCIOSPHERE_FIXTURE_ROOT` — checkout or mounted root for `SocioProphet/sociosphere`.

Optional:

- `OSM_MAP_API_HOST` — default `127.0.0.1`.
- `OSM_MAP_API_PORT` — default `8088`.
- `OSM_MAP_API_CORS_ALLOWED_ORIGINS` — comma-separated browser origins allowed to call the API. Empty by default, which disables CORS preflight handling.
- `OSM_MAP_API_CORS_ALLOW_CREDENTIALS` — `true` only when the configured browser origin must send credentials. Default `false`.

## Browser / Vue shell integration

The Vue product shell calls the API through `VITE_GAIA_MAP_API_BASE`.

Local development shape:

```bash
cd apps/osm-map-api
export GAIA_FIXTURE_ROOT="$HOME/dev/gaia-world-model"
export SHERLOCK_FIXTURE_ROOT="$HOME/dev/sherlock-search"
export SOCIOSPHERE_FIXTURE_ROOT="$HOME/dev/sociosphere"
export OSM_MAP_API_HOST=127.0.0.1
export OSM_MAP_API_PORT=8088
export OSM_MAP_API_CORS_ALLOWED_ORIGINS="http://localhost:5174"
python3 -m osm_map_api
```

Then the Vue shell should set:

```bash
VITE_GAIA_MAP_API_BASE=http://127.0.0.1:8088
```

The current Vue shell also supports deterministic demo fallback mode. Fallback mode is for product demonstration when this API is not reachable; it is not a production data plane and it does not replace API readiness.

Suggested environment mapping:

| Environment | `VITE_GAIA_MAP_API_BASE` | `OSM_MAP_API_CORS_ALLOWED_ORIGINS` |
| --- | --- | --- |
| local API direct | `http://127.0.0.1:8088` | `http://localhost:5174` |
| local Vite proxy | `/api` | not required if same-origin proxy is used |
| preview/staging | staging API URL | staging app origin |
| production | production API URL or same-origin gateway path | production app origin |

Do not use `*` with credentialed browser access. Prefer explicit origins and same-origin gateway/proxy deployment when possible.

## Health and readiness

- `GET /healthz` reports process liveness only.
- `GET /readyz` verifies required fixture roots and fails with `503` when the API cannot serve the GAIA/OSM fixture-backed contract.

The Vue shell may render demo fallback when the API is not ready, but operators should still treat `/readyz != ready` as a backend issue.

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
