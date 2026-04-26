# GAIA / OFIF / MeshLab / Control Tower Master Plan

Status: v0 integrated build plan
Owner surface: prophet-platform
Date: 2026-04-26

## Purpose

This master plan integrates the current SocioProphet workstreams into one buildable platform plan.

The goal is to build a local-first, mesh-ready, evidence-first, agentic operating and intelligence platform that combines:

- GAIA world modeling and geospatial digital twins;
- OFIF field intelligence and trusted sensor/event envelopes;
- MeshRush graph-native agent operation;
- SourceOS / nlboot host lifecycle, boot, recovery, update, rollback;
- Lampstand local state sampling and percolation;
- Sherlock Search discovery and audit retrieval;
- Lattice Forge reproducible runtime/package provenance;
- Agentplane governed execution and replay;
- SocioSphere workspace/fleet governance;
- open industrial IoT / supply-chain control tower capabilities;
- navigation and transportation infrastructure intelligence;
- home IoT / KubeEdge / edge mesh support.

## One-sentence doctrine

Local state becomes governed evidence; governed evidence becomes world-state; world-state becomes searchable, reproducible, graph-operable intelligence; agentic action only happens through policy-bound execution and replay.

## Layer map

| Layer | Primary repo | Responsibility |
| --- | --- | --- |
| Platform contracts/services | `SocioProphet/prophet-platform` | master plan, shared schemas, platform API seams, product control surfaces |
| Workspace/fleet governance | `SocioProphet/sociosphere` | composition, validation gates, workspace/fleet registration, policy conformance |
| Host lifecycle | `SociOS-Linux/nlboot`, SourceOS repos | boot, recovery, enrollment, update, rollback, BootReleaseSet |
| Governed execution | `SocioProphet/agentplane` | validate -> run -> evidence -> replay -> rollout |
| Graph-native agent ops | `SocioProphet/meshrush` | graph entry, diffusion, crystallization, bounded compilation, evidence traces |
| World model | `SocioProphet/gaia-world-model` | geospatial/world-state/evidence/simulation/action semantics |
| Field intelligence | `SocioProphet/orion-field-intelligence` | OFIF EventEnvelope, observation, custody, comms, adversarial context |
| Local sampling | `SocioProphet/lampstand` | local scan/index/watch/reconcile, LocalStateRecord, percolation |
| Discovery | `SocioProphet/sherlock-search` | federated discovery, geospatial/evidence/runtime search records |
| Runtime provenance | `SocioProphet/lattice-forge` | RuntimeAsset, SBOM, lockfile, signature, scan, promotion evidence |

## Workstream 1 — GAIA geospatial/world model

Objective: make GAIA the canonical world-state, geospatial, evidence, ontology, model, simulation, and action layer.

Initial capabilities:

- OSM-backed base geography;
- STAC / COG / Zarr / NetCDF / GRIB / GeoParquet catalog strategy;
- H3 as first shared spatial key;
- OFIF event ingestion;
- soil intelligence use case;
- navigation and infrastructure intelligence;
- control tower asset/supply-chain twin;
- model validation surface successor to CyberConnector/COVALI;
- MeshLab successor to PlanetLab concepts.

Key artifacts already added in GAIA:

- `docs/integrations/OFIF_INTEGRATION.md`
- `contracts/mappings/ofif-to-gaia.v1.json`
- `contracts/mappings/gaia-to-ofif-context.v1.json`
- `gaia/ontology/imports/ofif.yaml`
- `docs/GAIA_ORION_SOIL_INTELLIGENCE_USE_CASE.md`
- `docs/integrations/LAMPSTAND_LOCAL_STATE_INTEGRATION.md`
- `docs/integrations/SHERLOCK_SEARCH_INTEGRATION.md`
- `docs/integrations/LATTICE_FORGE_INTEGRATION.md`
- `docs/integrations/CYBERCONNECTOR_SUCCESSOR_STRATEGY.md`
- `docs/integrations/PRINCETON_PLANETLAB_SUCCESSOR_STRATEGY.md`
- `docs/integrations/NAVIGATION_INFRASTRUCTURE_INTELLIGENCE.md`
- `docs/integrations/OPEN_INDUSTRIAL_IOT_SUPPLY_CHAIN_CONTROL_TOWER.md`
- `schemas/navigation/*`
- `schemas/local-state/*`
- `schemas/search/gaia_sherlock_record.v1.schema.json`
- OFIF bridge and soil-intelligence fixture/scripts.

Next build tasks:

1. Add state-of-the-art integration map.
2. Add model/simulation/data-product schemas.
3. Add navigation decision card and Lattice runtime fixture.
4. Add control-tower schemas.
5. Add mesh schemas.

## Workstream 2 — OFIF field intelligence

Objective: make Orion Field Intelligence Framework the trusted event layer for field, IoT, edge, custody, comms, and adversarial observations.

Current role:

- EventEnvelope authority;
- ObservationEvent authority;
- custody/comms/adversarial metadata;
- defensive governance primitives;
- field event -> GAIA evidence path.

Key artifacts already added:

- `docs/integrations/GAIA_INTEGRATION.md`
- `ontology/gaia-bindings.ttl`
- `fixtures/observation-event.sample.v1.json`

Next build tasks:

1. Add Home IoT / Matter / Home Assistant event binding doc.
2. Add SensorThings/SOSA/SSN binding schema.
3. Add asset-health OFIF event fixture.
4. Add navigation anomaly OFIF event fixture.

## Workstream 3 — Lampstand local sampling and percolation

Objective: make Lampstand the local-state sampler and percolation membrane.

Current role:

- scan/watch/reconcile local state;
- local FTS/search;
- local metadata and hashes;
- emit LocalStateRecord and PercolationEnvelope;
- percolate to GAIA/OFIF/Sherlock/Lattice only through policy.

Next build tasks:

1. Mirror LocalStateRecord schema into Lampstand.
2. Add local-state -> Sherlock fixture.
3. Add local LiDAR file -> GAIA navigation evidence fixture.
4. Add health/stats percolation record.

## Workstream 4 — Sherlock Search discovery

Objective: make Sherlock the discovery and audit retrieval layer for documents, local records, geospatial evidence, field events, decision cards, runtime assets, and mesh experiments.

Key artifacts already added:

- `schemas/sherlock_geospatial_result.v1.schema.json`
- `examples/gaia-soil-intelligence-decision-card.sherlock-result.v1.json`
- `tools/validate-geospatial-result.js`
- `.github/workflows/geospatial-result.yml`

Next build tasks:

1. Add navigation infrastructure decision-card Sherlock result fixture.
2. Add runtime asset search result fixture.
3. Add endpoint or adapter route for loading static example records.
4. Add scoring contract for spatial/temporal/evidence/runtime ranking.

## Workstream 5 — Lattice Forge runtimes

Objective: make Lattice Forge the reproducible runtime, package, model, and pipeline provenance boundary.

Current role:

- RuntimeAsset;
- lockfile/provenance -> build artifact -> signed runtime release;
- SBOM, signatures, scans, promotion state;
- GAIA/OFIF bridge runtime;
- soil intelligence runtime;
- navigation LiDAR/routing runtime;
- control tower anomaly runtime.

Existing issue:

- `SocioProphet/lattice-forge#6` — GAIA / OFIF soil-intelligence runtime asset path.

Next build tasks:

1. Add GAIA soil runtime fixture directly to Lattice Forge.
2. Add navigation LiDAR feature extraction runtime fixture.
3. Add control tower anomaly scoring runtime fixture.
4. Add runtime validation examples aligned with existing RuntimeAsset schema.

## Workstream 6 — MeshRush graph-native agent operation

Objective: make MeshRush the graph-operating runtime over Gaia/OFIF/Lampstand/Sherlock/Lattice/SocioSphere graph views.

Current role from MeshRush charter:

- graph entry and traversal;
- diffusion/exploration;
- grounding;
- stop conditions;
- crystallization/bounded compilation;
- evidence/traces;
- graph-view interfaces derived from typed hypergraph world model.

Next build tasks:

1. Add Gaia/OFIF graph view integration doc in MeshRush.
2. Add example: soil intelligence graph diffusion -> crystallized evidence cluster.
3. Add example: navigation corridor risk graph -> bounded compilation artifact.
4. Add adapter contract to Agentplane execution.

## Workstream 7 — SourceOS / nlboot / KubeEdge / Home IoT

Objective: provide local-first host/edge lifecycle, boot/recovery/update, optional Kubernetes-native edge substrate, and home/facility IoT integration.

Roles:

- SourceOS: host OS/lifecycle;
- nlboot: boot/recovery/provisioning primitive;
- KubeEdge: optional Kubernetes-native edge substrate for managed fleets;
- Home Assistant/Matter/Thread/MQTT: home/facility local device fabric;
- OFIF: wraps device/field events;
- Gaia: models home/facility/asset twin;
- MeshRush: reasons over the graph;
- Agentplane: governs actions.

Next build tasks:

1. Add `MESHRUSH_KUBEEDGE_HOME_IOT_INTEGRATION.md`.
2. Add HomeFabricRecord schema.
3. Add DeviceTwinRecord schema.
4. Add AutomationPolicyRecord schema.
5. Add SourceOS/KubeEdge optional substrate doc in SocioSphere.

## Workstream 8 — Open industrial IoT and supply-chain control tower

Objective: build an open, evidence-first successor to Watson IoT / Maximo / Sterling-style capabilities.

Core objects to add:

- AssetTwinRecord;
- AssetHealthObservation;
- WorkOrderCandidate;
- InventoryNodeRecord;
- InventoryEvent;
- ControlTowerDecisionCard;
- RiskExposureRecord;
- ComplianceRequirement;
- ApprovalRecord.

Next build tasks:

1. Add control tower schemas.
2. Add navigation asset health card fixture.
3. Add OFIF asset health event fixture.
4. Add Sherlock result fixture.
5. Add Lattice runtime fixture.

## Workstream 9 — Navigation and transportation infrastructure intelligence

Objective: build open navigation, HD map, LiDAR, rail/road/bridge/station asset intelligence, route planning, and infrastructure decision support.

Already added:

- `schemas/navigation/transport_infrastructure_asset.v1.schema.json`
- `schemas/navigation/route_plan.v1.schema.json`
- `schemas/navigation/lidar_corridor_observation.v1.schema.json`
- `fixtures/navigation/rail-corridor-lidar-observation.sample.v1.json`
- `fixtures/navigation/multimodal-route-plan.sample.v1.json`

Next build tasks:

1. Add infrastructure decision-card schema/fixture.
2. Add Sherlock result fixture.
3. Add Lattice runtime fixture.
4. Add OFIF navigation anomaly event fixture.

## Workstream 10 — Governance, privacy, safety, and evaluation

Objective: make every action auditable, safe, privacy-aware, benchmarkable, and governance-bound.

Objects to add:

- PrivacyImpactAssessment;
- SurveillanceRiskClassification;
- NavigationSafetyCase;
- StreamContract;
- BenchmarkManifest;
- DigitalTwinCapabilityProfile;
- DataProductManifest;
- ResearchObjectPackage.

## Build order

### Phase 0 — Contract consolidation

Create one shared plan and progress ledger. Lock the schemas that downstream work uses.

### Phase 1 — Proof chain expansion

Demonstrate:

```text
OFIF event -> GAIA artifact -> soil fusion -> decision card -> Sherlock record -> Lattice runtime reference
```

Then extend to:

```text
Lampstand local sample -> PercolationEnvelope -> GAIA / OFIF / Sherlock / Lattice
```

Then extend to:

```text
Navigation LiDAR observation -> route/infrastructure risk -> decision card -> search/runtime evidence
```

### Phase 2 — Mesh and control tower

Add MeshNodeRecord, SliceAllocationRecord, AssetTwinRecord, InventoryEvent, ControlTowerDecisionCard.

### Phase 3 — Agentic graph operation

MeshRush graph views over Gaia/OFIF/Lampstand/Sherlock/Lattice records. Agentplane executes only approved actions.

### Phase 4 — SourceOS / edge / home IoT integration

Home IoT and KubeEdge optional substrate are wired into OFIF/Gaia/MeshRush/Agentplane.

### Phase 5 — Product surface

Prophet Platform dashboard: devices, assets, routes, evidence, models, runtimes, search, decisions, approvals.

## Progress tracking rule

Every implementation turn should report:

1. Files changed.
2. Commits or issues created.
3. Workstream progress.
4. Current blockers or uncertainty.
5. Next two concrete actions.

## Current status snapshot

- GAIA/OFIF bridge: contract + fixtures + bridge script + CI path started.
- Sherlock geospatial/evidence result: schema + example + validator + CI added.
- Lattice Forge runtime path: Gaia fixture + tracking issue added.
- Lampstand integration: local sampling/percolation contract and schemas added in Gaia.
- CyberConnector successor: strategy added.
- PlanetLab successor: strategy added.
- Navigation infrastructure intelligence: strategy, schemas, and fixtures added.
- Control tower strategy: added.
- MeshRush/KubeEdge/Home IoT: mapped conceptually; concrete docs/schemas still pending.
