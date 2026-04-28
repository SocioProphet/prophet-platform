# GAIA / OpenStreetMap Core Thesis Retirement Plan

Status: active closure plan
Date: 2026-04-27
Owner surface: Prophet Platform

## Core thesis

GAIA must become a production-grade open world-model map surface:

```text
OpenStreetMap base geography
  -> GAIA entity and ontology bindings
  -> tile/layer surface
  -> feature inspection
  -> LiDAR/remote-sensing/field evidence fusion
  -> Sherlock discovery
  -> control-tower decision support
  -> governed runtime admission only when hardened
```

The goal is not to keep writing governance documents. The goal is to retire the first production slice as demo-able, testable, and safe.

## Retirement target

This workstream is retired when the first OSM/GAIA map slice can demonstrate:

1. OSM-derived GAIA features are served by Prophet Platform.
2. OSM attribution is preserved and visible.
3. Map/tile layer metadata is available through a production-shaped API.
4. OSM feature inspection works by OSM ID and H3 cell.
5. Route graph output is explicitly advisory unless validated.
6. LiDAR-derived rail corridor evidence is discoverable and bound to a safety case.
7. Sherlock can search OSM and LiDAR evidence records.
8. MeshRush can crystallize the navigation evidence graph.
9. Agentplane receives approval-required review candidates for non-runnable actions.
10. Lattice Forge admission is explicitly blocked until runtime packaging is hardened.

## What is already done

### GAIA world model

- OSM integration contract.
- OSM feature binding schema and fixture.
- Map tile layer manifest schema and fixture.
- OSM route graph manifest schema and fixture.
- OSM ingestion executable proof.
- OSM tile export executable proof.
- OSM route graph executable proof.
- LiDAR corridor observation fixture.
- LiDAR feature extraction executable proof.
- LiDAR-derived infrastructure asset fixture.
- Navigation safety-case schema and advisory fixture.
- LiDAR rollback plan schema and fixture.
- Malformed LiDAR input fixture.
- Contract validation and CI coverage.

### Prophet Platform

- OSM platform requirements.
- OSM map/tile/routing acceptance criteria.
- OSM control-surface requirements.
- OSM static fixture API requirements.
- `apps/osm-map-api` production-shaped FastAPI scaffold.
- Health/readiness endpoints.
- Map layer, feature lookup, H3 lookup, route graph, runtime boundary, governance, and Sherlock search endpoints.
- Response receipts with attribution/provenance/safety metadata and deterministic digests.
- Tests, CI, Dockerfile, and Kubernetes scaffold.

### Sherlock

- OSM-derived map-layer result.
- LiDAR-derived infrastructure evidence result.
- Geospatial/evidence result validation expanded across all examples.

### MeshRush

- Soil crystallization fixture.
- Navigation corridor LiDAR crystallization fixture.
- Validator expanded across graph-view fixtures.
- Approval-boundary validation.

### SocioSphere / SourceOS edge governance

- OSM attribution policy and validator.
- Strict OSM attribution workflow.
- KubeEdge optional-substrate governance.
- Edge host lifecycle schema, fixture, validator, and CI.

### Lattice Forge

- OSM runtime admission issue opened.
- LiDAR runtime admission issue opened.
- No premature runtime assets admitted.

## Remaining closure work

### P0 — required to retire the core thesis

1. Fix or bypass Agentplane PR #54 merge blocker.
2. Add Agentplane navigation corridor review candidate to PR #54 or successor PR.
3. Confirm `osm-map-api` CI is green after receipt and OpenAPI changes.
4. Confirm GAIA contract fixture CI is green after LiDAR rollback and safety-case changes.
5. Add a simple demo runbook that runs the static OSM API and points it at GAIA/Sherlock/SocioSphere fixture roots.
6. Add one top-level README section or docs page that tells a reviewer how to demo:
   - map layer catalog;
   - OSM feature inspection;
   - H3 search;
   - route graph advisory status;
   - LiDAR evidence result;
   - runtime boundary status;
   - governance state.

### P1 — important, but not retirement-blocking

1. Add generated OpenAPI artifact if the team wants checked-in OpenAPI.
2. Add `osm-map-api` fixture bundle packaging for local demo.
3. Add a MapLibre UI stub or wire existing UI to `/map-layers` and feature lookup endpoints.
4. Add safety-case search as a separate Sherlock result if reviewers need it distinct from LiDAR evidence.
5. Add Lattice RuntimeAsset target-shape docs for OSM and LiDAR without admitting assets.

### P2 — later hardening

1. SBOM/signing/attestation pipeline.
2. Production OSM PBF/Overpass input adapters.
3. Real tile generation backend.
4. Real point-cloud/COPC processing backend.
5. Validated safety-case and authority approval flows.
6. Smart Spaces domain-home decision.

## Closure definition

The core thesis can be considered retired when P0 is complete and the demo runbook succeeds against checked-out repos.

Do not keep expanding scope into Smart Spaces, Lattice runtime packaging, or full production tile generation until the P0 demo path is complete.

## Immediate execution order

1. Resolve Agentplane PR #54 blocker or open successor PR.
2. Add/verify Agentplane navigation corridor candidate.
3. Add demo runbook in Prophet Platform.
4. Verify CI surfaces.
5. Update progress ledger to mark core thesis as retirement-ready or identify exact failed checks.
