# Atlas Integration for Lattice Studio

This note registers the SocioProphet Atlas repositories as first-class inputs to the Lattice Studio, catalog, local-dev, PaaS DevOps, and agentic workflow lanes.

## Repositories found

### SocioProphet/atlas_master_bundle_complete

Atlas Master Bundle with TritRPC v1, `atlas_service`, model/study scripts, Beam + Airflow orchestration boilerplates, Avro schemas, pipelines, DAGs, observability, and Grafana starter assets.

Primary integration use:

```text
model studies
Beam/Airflow data workflows
TritRPC service surface
observability starter assets
```

### SocioProphet/atlas_os_service_full

Atlas OS Service with TritRPC v1 proto, OS daemon scaffold, admission, DRF scheduler, Ray runner, registry, ServeService stubs, router/autoscaler/sticky routing notes, Prometheus/Loki/Grafana observability, and tests.

Primary integration use:

```text
SourceOS/SociOS local service lane
Ray runner lane
local registry
admission/scheduler lane
service observability
```

### SocioProphet/atlas_master_bundle_autopilot_fullorchestration

Atlas Master Bundle with TritRPC service, semantic constraints, Autopilot promotion/rollout, ontology, A2A Avro envelope, Beam/Airflow orchestration, Grafana dashboards, and alert policies.

Primary integration use:

```text
autopilot promotion/rollout
ontology + SHACL governance
A2A workflow envelopes
Beam/Airflow orchestration
per-tenant observability/alerting
```

## Lattice Studio alignment

Atlas should not live beside Lattice Studio as a disconnected bundle. It should become part of the same asset graph:

```text
CatalogAsset
  -> RuntimeAsset
  -> NotebookSession
  -> PaaSDeploymentPlan
  -> Atlas workflow/service context
  -> PlatformAssetRecord
  -> Sherlock/Topics/New Hope/Policy/Contract/Graphbrain
```

## Required catalog asset classes

Atlas introduces additional concrete asset classes beyond data/model/app/service:

```text
atlas-service
atlas-study
atlas-workflow
atlas-ontology
atlas-a2a-envelope
atlas-observability-dashboard
atlas-autopilot-rollout
```

These should become `CatalogAsset.assetType` extensions or specialized platform records.

## Required workflow links

Lattice Studio must be able to bind a notebook or deployment plan to:

```text
atlasServiceRef
atlasStudyRef
beamPipelineRef
airflowDagRef
rayRunnerRef
a2aEnvelopeRef
ontologyRef
shaclConstraintRef
observabilityDashboardRef
promotionRolloutRef
```

## Local SourceOS/SociOS developer surface

Atlas OS Service is the strongest local-dev link. It should align with:

```text
local notebook session
terminal session
browser surface
coding agent session
SourceOS service runner
Ray runner
registry/admission/scheduler
```

The next SourceOS/SociOS integration should create a `LocalDevSession` contract that can attach to Atlas OS Service capabilities.

## Porter / PaaS DevOps lane

The Porter-style PaaS lane should treat Atlas Autopilot as a possible promotion/rollout backend.

```text
PaaSDeploymentPlan
  -> Atlas autopilot promotion plan
  -> Kubernetes/Helm target
  -> route
  -> observability
  -> rollback evidence
```

## Memory mesh lane

Atlas study/workflow/service activity must emit memory events.

Minimum memory bindings:

```text
NotebookSession -> MemoryEvent
PaaSDeploymentPlan -> MemoryEvent
AtlasStudy -> MemoryEvent
AtlasWorkflow -> MemoryEvent
AtlasService -> MemoryEvent
```

## Immediate implementation targets

1. Add Atlas refs to Lattice Studio PaaSDeploymentPlan or adjacent AtlasContext.
2. Add Atlas catalog asset fixtures for service, study, workflow, ontology, A2A, observability, and autopilot rollout.
3. Add SourceOS/SociOS `LocalDevSession` contract that can attach to Atlas OS Service.
4. Add memory mesh sidecar output for notebook/session/deployment/Atlas activity.
5. Add Sherlock indexing for Atlas-derived platform records.
