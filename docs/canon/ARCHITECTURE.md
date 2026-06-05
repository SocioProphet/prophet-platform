# Canon Architecture v0.1

Canon is the governed source, dataset, task, application, receipt, community-intelligence, and data-product registry inside Prophet Platform.

Canon is not a standalone product repository. It is a deployable platform capability. The prior `prophet-core-catalog` concept is treated as a consolidation candidate and should collapse into the platform unless a separate lifecycle is proven.

## Naming decision

Use `Canon` as the subsystem name.

Avoid `Alexandria`, `Atlas`, `DataHub`, and religious-object names. Canon means accepted authority, rule, measure, and standard. That maps directly to canonical sources, canonical manifests, policy admissibility, source authority, lineage receipts, and data-product eligibility.

## Problem statement

The durable lesson from earlier data-platform work is that users do not primarily care about storage backends, query engines, schemas, lakehouse mechanics, or distributed-system internals. They care about tasks:

- find the right source;
- ingest data;
- clean and normalize it;
- join it with other sources;
- resolve entities;
- inspect quality and policy constraints;
- visualize and explain it;
- share it with a team;
- publish it as a governed product;
- prove where it came from and how it changed.

Canon exists to make those tasks discoverable, auditable, and executable through Prophet Platform.

## Community data layer

Canon Commons is the community intelligence layer of Prophet Platform.

Members contribute local, operational, domain, workflow, and product signals. Canon converts eligible contributions into anonymized, aggregated, policy-admitted community intelligence. The community can then understand itself without exposing raw member data by default.

Raw data remains private, tenant-bound, client-owned, licensed, or permissioned unless explicitly published. Community intelligence is shared by default only after aggregation, anonymization, policy admission, and receipt generation.

## Canon object model

Canon defines the following platform objects.

- Source: an external, open, licensed, client-owned, or internal feed with license, auth, freshness, provenance, and policy metadata.
- Dataset: a versioned, normalized data asset derived from one or more sources.
- Collection: a workspace-visible grouping of datasets, notebooks, apps, visualizations, and receipts.
- Task: a user-oriented operation such as ingest, clean, join, enrich, resolve, summarize, visualize, model, publish, audit, or export.
- Catalog app: a task processor implemented by an API, workflow, notebook, agent, script, container, or external system.
- Receipt: durable evidence for source access, transform, validation, policy decision, publication, or export.
- Product pack: governed bundle of datasets, tasks, apps, policies, and receipts exposed through SocioProphet product surfaces.
- Coverage record: a domain/topic/assertion/source/evidence mapping that states what Canon can responsibly cover.
- Commons aggregate: a privacy-preserving community-level metric, benchmark, trend, gap, or assertion admitted for shared use.

## Platform placement

Canon should live under Prophet Platform, initially as:

- `services/canon/registry/`
- `services/canon/sources/`
- `services/canon/datasets/`
- `services/canon/tasks/`
- `services/canon/apps/`
- `services/canon/receipts/`
- `services/canon/product-packs/`
- `services/canon/commons/`
- `services/canon/coverage/`
- `registry/canon/`
- `docs/canon/`

The current architecture document is the planning anchor before code relocation.

## Integration boundaries

Canon owns registry semantics, object identity, manifest vocabulary, search facets, task metadata, admissibility metadata, coverage metadata, sharing modes, and data-product packaging metadata.

Execution is delegated:

- Prophet Platform runs the deployable services.
- Prophet Core Ingest functionality should collapse into platform ingestion services.
- Prophet Core Query functionality should collapse into platform query/search services.
- Prophet Core Infra functionality should collapse into platform deployment/infra modules.
- Prophet Ledger or `prophet-core-ledger` remains a separate audit candidate until receipt durability and audit lifecycle are settled.
- Policy Fabric and Guardrail Fabric decide policy admission and guardrail enforcement.
- AgentPlane runs governed agent tasks.
- Sherlock, Holmes, SynapseIQ, Slash Topics, New Hope, and Lampstand expose discovery, reasoning, and retrieval surfaces.
- SocioSphere tracks workspace/service-register awareness and downstream propagation.

## Non-goals

Canon is not a generic metadata list, not a clone of MIT DataHub, not LinkedIn/Acryl DataHub, not CKAN, not a data marketplace by itself, not a raw cross-tenant query system, and not a notebook runtime.

Canon is the registry kernel that lets these other systems become coherent, governed, searchable, productizable, and community-understandable.

## First implementation slice

The first slice should remain design-first and low-risk:

1. Establish Canon naming and boundaries.
2. Define the platform object vocabulary.
3. Define Canon Commons as the community intelligence layer.
4. Seed the coverage model, domains, assertion types, sharing modes, source candidates, and coverage matrix.
5. Mark standalone core catalog/ingest/query/infra repos as consolidation candidates.
6. Add a migration map into Prophet Platform.
7. Delay physical repo archival until import paths, CI, release behavior, and downstream consumers are known.
