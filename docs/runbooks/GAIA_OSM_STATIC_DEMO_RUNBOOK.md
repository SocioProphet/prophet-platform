# GAIA / OSM Static Demo Runbook

Status: v0 demo runbook
Owner surface: Prophet Platform

## Purpose

This runbook demonstrates the first retire-able GAIA / OpenStreetMap product slice:

- OSM-derived GAIA feature binding;
- map/tile layer metadata;
- OSM feature inspection;
- H3 spatial lookup;
- advisory OSM route graph;
- LiDAR-derived infrastructure evidence;
- runtime boundary state;
- SocioSphere governance state;
- Sherlock discovery records.

This demo is read-only and fixture-backed. It does not require a production tile server, live OSM ingestion, or Lattice runtime admission.

## Required local checkouts

Expected repo layout:

```text
~/dev/prophet-platform
~/dev/gaia-world-model
~/dev/sherlock-search
~/dev/sociosphere
```

## Start the API

```bash
cd ~/dev/prophet-platform/apps/osm-map-api
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[test]'

export GAIA_FIXTURE_ROOT=~/dev/gaia-world-model
export SHERLOCK_FIXTURE_ROOT=~/dev/sherlock-search
export SOCIOSPHERE_FIXTURE_ROOT=~/dev/sociosphere
export OSM_MAP_API_HOST=127.0.0.1
export OSM_MAP_API_PORT=8088

python3 -m osm_map_api
```

## Verify service health

```bash
curl -fsS http://127.0.0.1:8088/healthz
curl -fsS http://127.0.0.1:8088/readyz
```

Expected readiness:

```json
{"status":"ready"}
```

If `/readyz` fails, check the three fixture-root environment variables and confirm the required fixtures exist.

## Demo flow

### 1. Map layer catalog

```bash
curl -fsS http://127.0.0.1:8088/map-layers | jq .
```

Reviewer should see:

- `GAIA OSM Demo Road Layer`;
- `layer_type=vector`;
- tile URL template;
- attribution text;
- source/provenance refs;
- response receipt with digest.

### 2. Layer detail

```bash
curl -fsS http://127.0.0.1:8088/map-layers/gaia-osm-demo-road-layer-v1 | jq .
```

Reviewer should confirm:

- MapLibre-compatible metadata;
- OSM attribution present;
- H3 coverage present;
- provenance refs present.

### 3. OSM feature inspection

```bash
curl -fsS http://127.0.0.1:8088/features/by-osm/way/424242 | jq .
```

Reviewer should confirm:

- OSM type and ID are preserved;
- OSM tags are visible;
- GAIA entity binding exists;
- routing status remains advisory;
- response receipt carries attribution and source refs.

### 4. H3 spatial search

```bash
curl -fsS http://127.0.0.1:8088/features/by-h3/8928308280fffff | jq .
```

Reviewer should see matching OSM-derived feature and layer records.

### 5. Advisory route graph

```bash
curl -fsS http://127.0.0.1:8088/route-graphs/osm | jq .
```

Reviewer should confirm:

- route graph exists;
- `safety_status=advisory`;
- no safety-critical routing claim is made;
- attribution and provenance are present.

### 6. Runtime boundary state

```bash
curl -fsS http://127.0.0.1:8088/runtime-boundaries/osm | jq .
```

Reviewer should confirm:

- OSM ingestion runtime is executable-proof only;
- OSM route graph runtime is executable-proof only;
- OSM tile export runtime is executable-proof only;
- Lattice admission is not granted.

### 7. Governance state

```bash
curl -fsS http://127.0.0.1:8088/governance/osm | jq .
```

Reviewer should confirm:

- OSM validation lane exists;
- attribution is required;
- unresolved blockers are explicit.

### 8. Sherlock OSM search record

```bash
curl -fsS http://127.0.0.1:8088/search/osm-demo | jq .
```

Reviewer should confirm:

- `entity_type=MAP_LAYER`;
- H3/OSM spatial refs;
- evidence/provenance refs;
- `open_map=true`.

## GAIA executable proofs

From `~/dev/gaia-world-model`:

```bash
python3 scripts/validate_contract_fixtures.py
python3 scripts/validate_multidomain_fixtures.py

python3 geospatial/osm_ingest.py \
  fixtures/geospatial/osm-way-input.sample.v1.json \
  /tmp/osm-feature-bindings.json

python3 geospatial/osm_tile_export.py \
  fixtures/geospatial/osm-road-feature-binding.sample.v1.json \
  /tmp/osm-derived-map-tile-layer.json

python3 geospatial/osm_route_graph.py \
  fixtures/geospatial/osm-road-feature-binding.sample.v1.json \
  /tmp/osm-route-graph.json

python3 navigation/lidar_feature_extract.py \
  fixtures/navigation/rail-corridor-lidar-observation.sample.v1.json \
  /tmp/lidar-derived-infrastructure-assets.json

python3 navigation/lidar_rollback_receipt.py \
  fixtures/navigation/lidar-runtime-rollback-plan.sample.v1.json \
  /tmp/lidar-rollback-receipt.json
```

## Fail-closed LiDAR malformed-input proof

From `~/dev/gaia-world-model`:

```bash
set +e
python3 navigation/lidar_feature_extract.py \
  fixtures/navigation/rail-corridor-lidar-observation.malformed-missing-point-cloud.sample.v1.json \
  /tmp/lidar-malformed-output.json
status=$?
set -e
[ "$status" -ne 0 ] && echo "malformed LiDAR input failed closed"
```

Expected result: non-zero exit status.

## Sherlock validation

From `~/dev/sherlock-search`:

```bash
for record in examples/*.sherlock-result.v1.json; do
  node tools/validate-geospatial-result.js "$record"
done
```

## MeshRush validation

From `~/dev/meshrush`:

```bash
python3 tools/validate_crystallization_fixtures.py
```

## Agentplane status

Agentplane PR #54 contains the MeshRush adapter contract and candidate fixtures, including the navigation-corridor approval-required candidate.

Known blocker: required `lint` status-context mismatch still blocks merge even when visible Actions jobs are green.

## Retirement checklist

The core thesis is retirement-ready when:

- OSM Map API tests pass;
- GAIA contract fixture CI passes;
- Sherlock geospatial result validation passes;
- MeshRush graph-view validation passes;
- Agentplane adapter is merged or explicitly accepted as blocked by branch protection only;
- this runbook succeeds against local checkouts.

## Non-goals for this demo

- production OSM tile server;
- live Overpass/PBF ingestion;
- Lattice RuntimeAsset admission;
- safety-critical navigation;
- Smart Spaces domain implementation.
