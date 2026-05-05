# KMaaS Repository Responsibility Map

## Purpose

This map prevents KMaaS from becoming another cross-repo idea with no owner. Each surface has a primary repo, secondary contributors, and an explicit handoff contract.

## Responsibility table

| Surface | Primary owner | Secondary contributors | Output |
|---|---|---|---|
| Product/runtime surface | `prophet-platform` | `agentplane`, `sociosphere` | KMaaS routes, dashboards, proof-pack viewer, phase status |
| Domain ontology | `ontogenesis` | standards repos, product teams | domain backbone, KPI object, evidence span, policy envelope terms |
| Normative schemas | standards repos | `prophet-platform`, `agentplane` | metric contract, phase gate, proof pack, KPI pack schemas |
| Execution receipts | `agentplane` | `TriTRPC`, `sociosphere` | run artifacts, placement receipts, replay manifests |
| Workspace orchestration | `sociosphere` | `agentplane`, `prophet-platform` | engagement workflow, workspace lock, onboarding state |
| Governed context packs | `slash-topics` | `sociosphere`, `agentplane` | topic pack identity, provenance, locality, cache/fetch events |
| Deterministic transport | `TriTRPC` | `agentplane` | policy/evidence references, receipt refs, replay refs, transport metadata |
| Human approval / consent | `human-digital-twin` | `policy-fabric`, `agentplane` | policy/approval events, attestation refs, human-governed replay expectations |
| Linux packaging | `SourceOS-Linux`, `SociOS-Linux` | `prophet-platform` | local-first service profile, system integration, offline proof-pack path |

## Near-term integration order

1. Land product doctrine in `prophet-platform/docs/kmaas/`.
2. Land normative schemas in the standards repository.
3. Add ontology terms and SHACL/JSON-LD examples in `ontogenesis`.
4. Wire KMaaS receipt/proof-pack names into `agentplane`.
5. Add engagement workflow templates to `sociosphere`.
6. Bind context-pack events in `slash-topics`.
7. Expose dashboard surfaces in `prophet-platform`.
8. Carry packaged runtime into SourceOS/SociOS after product contracts stabilize.

## Handoff contracts

### Standards to platform

Standards repos publish schemas and examples. `prophet-platform` consumes pinned versions and exposes runtime views. The platform must not silently drift from standards-layer contracts.

### Sociosphere to AgentPlane

Sociosphere owns workspace truth: manifest ID, lock digest, dependency references, and onboarding state. AgentPlane owns execution truth: placement decision, run artifact, evidence seal, and replay manifest.

### Slash Topics to AgentPlane

Slash Topics owns context pack identity, locality, digest, cache/fetch events, and retrieval provenance. AgentPlane consumes those events into proof packs and run receipts.

### Human Digital Twin to AgentPlane

Human Digital Twin owns consent, approval, policy decision, and human-governed attestation events. AgentPlane consumes policy/approval references and must preserve them in replayable proof artifacts.

### TriTRPC to runtime services

TriTRPC owns deterministic transport envelopes and policy/evidence reference carriage. It does not own KPI semantics, domain ontology, or policy decisions.

## Out of scope for this package

- replacing existing MAIPJ/GAKW receipt work;
- moving all standards into `prophet-platform`;
- implementing runtime code before schemas are frozen;
- treating SourceOS/SociOS packaging as the first landing zone.

## First implementation epic

The first implementation epic should produce a Phase 1 text-only KMaaS baseline:

- one anchor domain;
- one system-of-record manifest;
- one bounded text corpus;
- one metric contract record;
- one phase-gate record;
- one proof pack;
- one audit-readable report;
- one replay or reproduction path.
