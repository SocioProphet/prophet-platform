# Prophet Platform Hosting Model

## Purpose

`prophet-platform` is the hosted composition surface for Sherlock and FogStack-enriched services. It is not the sole source-of-truth repository for every domain concern. It hosts, exposes, governs, and observes the live services the specification demands.

## Core rule

Separate:
- source implementation ownership
from
- runtime composition ownership

That yields the following model:

- `prophet-platform` owns deployment assembly, service catalog, overlays, operational composition, and hosted operator surfaces.
- adjacent Sherlock repositories remain the source-of-truth for specialized service logic.

## Hosted planes

Prophet Platform hosts and composes these planes:

- substrate plane
- control plane
- knowledge / evidence plane
- diagnostic plane
- action plane
- evolution plane

## Service classes

### Substrate services
These are required runtime dependencies, not end-user products.

- Matrix / Synapse support services
- Postgres
- Redis where needed
- OpenSearch
- NATS
- Keycloak
- OpenFGA
- OPA
- object storage
- OpenTelemetry Collector
- Temporal only when long-running workflows are live

### Core platform services
These are first-class hosted services.

- Identity Policy Service
- Search Evidence Service
- Case Triage Service
- Deep-Dive Orchestrator
- Topology Environment Service
- Artifact Release Service
- Evaluation Tournament Service
- Dashboard BFF

### Adapter services
These remain behind stable internal interfaces.

- GitHub adapter
- Google Drive adapter
- Artifact Registry adapter
- KubeEdge adapter
- Cilium / Hubble adapter
- Tetragon adapter

### Operator-facing applications
These are the human-visible surfaces.

- Matrix ChatOps shell integration
- Dashboard shell
- Deep-dive viewer
- Artifact browser
- Case console
- Topology explorer

## Boundary rules

- Search logic stays in the Search Evidence Service, not the dashboard.
- Room governance stays in shell / control-plane services, not search.
- Environment adapters stay behind stable contracts.
- Artifact promotion logic stays in the Artifact Release Service.
- Identity, attestation, and revocation stay centralized.

## Service-wave sequencing

### Wave 1
- Identity Policy Service
- Search Evidence Service
- Case Triage Service
- Deep-Dive Orchestrator
- Dashboard BFF
- Matrix shell integration
- Dashboard shell

### Wave 2
- Topology Environment Service
- Artifact Release Service

### Wave 3
- GitHub adapter
- Google Drive adapter
- Artifact Registry adapter
- KubeEdge adapter
- Cilium / Hubble adapter
- Tetragon adapter

## Platform doctrine

No production service without:
- explicit contract
- explicit owner
- explicit dependency list
- explicit secret source
- explicit observability package
- explicit rollback path
- explicit evidence outputs
- explicit replay or test fixture
