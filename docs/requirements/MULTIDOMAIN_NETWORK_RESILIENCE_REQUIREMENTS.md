# Multi-Domain Network Resilience and Accountability Requirements

Status: Draft v0.2
Scope: Prophet Platform, GAIA, SocioSphere, Sherlock, Agentplane, Lattice Forge

## Purpose

This document converts protocol and network-layer lessons from modern sensor-to-decision and sensor-to-effects systems into governance-oriented platform requirements.

The point is not to pretend defense, public-safety, or effects-linked stacks do not exist. The point is to make them accountable. The platform may support authorized sensing, monitoring, resilience, emergency response, environmental intelligence, infrastructure operations, logistics, public-safety accountability, defense governance, and customer-owned operational awareness.

The platform must not implement ungoverned targeting, autonomous weapon tasking, sensitive-site exploitation, evasion workflows, unauthorized tracking, or any execution path that bypasses policy approval, human authority, auditability, and legal basis.

## Governance posture

Defense/effects-linked systems are in governance scope.

Ungoverned effects execution is out of execution scope.

This distinction is mandatory. Runtime boundaries, network profiles, source feeds, identity overlays, decision artifacts, and operator actions must all be visible to governance. A system that can influence operational outcomes requires stronger accountability, not weaker observability.

## Source posture

The motivating network patterns are:

1. IP-native transport across heterogeneous bearers.
2. Multi-link PACE connectivity across local mesh, cellular, satellite, and fixed networks.
3. Tactical/operational gateways that bridge incompatible networks into governed data products.
4. Overlay security becoming the controlling boundary: identity, encryption, authorization, audit, and replay.
5. Failure modes caused by provider policy, cloud outage, RF disruption, GNSS/PNT failure, stale data, and software orchestration faults.
6. Runtime evidence and replay becoming mandatory for trust.

The platform adopts these as resilience, accountability, and governance requirements. It does not adopt them as ungated shooter-control requirements.

## Required platform abstractions

### 1. Link-agnostic transport profile

Every runtime or data product that consumes external telemetry SHOULD declare a transport profile.

The profile MUST include:

- transport family: local mesh, wired IP, cellular, SATCOM, file import, API pull, event stream, or offline package;
- network posture: none, restricted, allowlisted, live external, or classified-external;
- secret posture: none, static token, dynamic token, mTLS identity, hardware-backed identity, or external classified enclave;
- expected latency class;
- expected bandwidth class;
- disconnection tolerance;
- retry and backoff posture;
- store-and-forward behavior;
- clock/PNT dependency;
- source attribution requirement.

### 2. PACE network declaration

A production runtime that relies on live external data SHOULD define a PACE model:

- Primary path;
- Alternate path;
- Contingency path;
- Emergency/offline path.

The PACE model MUST NOT imply automatic escalation into unsafe action. It only describes data availability and continuity options.

### 3. Overlay security requirements

The platform MUST treat bearer networks as untrusted unless explicitly proven otherwise.

Every live-source runtime MUST define:

- identity model;
- authentication mechanism;
- authorization scope;
- encryption posture;
- source allowlist;
- operator or service account identity;
- audit log destination;
- export controls and redistribution policy;
- redaction/masking behavior;
- failure behavior when identity or authorization fails.

### 4. Time, PNT, and freshness semantics

Every observation or track-like record MUST carry explicit time semantics.

At minimum:

- observed time;
- received time when available;
- processed time when available;
- published time when available;
- clock source when known;
- freshness class;
- stale-data policy;
- PNT dependency note when relevant.

No runtime may promote a stale observation into an operational decision artifact without an explicit stale-data warning.

### 5. Runtime evidence and replay

Every executable runtime SHOULD emit a runtime evidence bundle conforming to `socioprophet-agent-standards`.

The bundle SHOULD include:

- input manifest;
- output manifest;
- input/output hashes;
- runtime ID;
- runtime class;
- policy posture;
- replay command;
- network posture;
- secret posture;
- sensitive-geospatial handling;
- source attribution and license refs.

### 6. Failure mode registry

Each live-source runtime SHOULD enumerate failure modes.

Required classes:

- source outage;
- provider policy interruption;
- network congestion;
- RF or local-link disruption when relevant;
- GNSS/PNT uncertainty when relevant;
- stale data;
- malformed input;
- identity/auth failure;
- authorization failure;
- downstream governance denial;
- replay failure.

### 7. Governance gates

The following conditions require explicit governance review before production use:

- live external feed access;
- restricted or customer-owned data;
- sensitive geospatial data;
- defense/public-safety data;
- effects-linked operational context;
- unmasks or precision restoration;
- writes to canonical stores;
- data export outside the workspace boundary;
- automatic work-order creation;
- any advisory artifact that could be mistaken for an operational command.

### 8. Accountability ledger requirements

Any effects-linked or defense/public-safety runtime MUST produce or reference an accountability ledger entry.

The entry SHOULD include:

- operator or service identity;
- authority/legal basis reference;
- mission or incident context reference;
- source data refs;
- evidence bundle refs;
- policy bundle hash;
- human approval state when required;
- redaction/masking state;
- freshness and PNT state;
- model/runtime version;
- replay procedure;
- downstream action or non-action disposition.

A runtime that cannot produce accountability evidence must remain blocked from production admission.

## Required integration updates

### GAIA

GAIA runtime boundary docs SHOULD add a `network_resilience` and `accountability` section for every live-capable runtime.

The section should declare:

- transport profile;
- PACE model;
- time/freshness semantics;
- source attribution;
- failure mode registry;
- evidence/replay posture;
- accountability ledger posture;
- human approval posture where relevant.

### SocioSphere

SocioSphere SHOULD validate that production runtime candidates include:

- network posture;
- secret posture;
- allowed source list;
- data license/redistribution policy;
- sensitive-geospatial handling;
- evidence/replay references;
- compliance doc references;
- authority/legal basis reference where defense/public-safety data is involved;
- accountability ledger output when effects-linked context exists.

### Agentplane

Agentplane SHOULD refuse execution candidates that:

- lack runtime evidence metadata;
- lack network/secret posture declarations;
- request live external feeds without policy authorization;
- request sensitive-geospatial unmasking without approval;
- attempt unsafe automatic tasking;
- omit required human approval state;
- omit accountability ledger references where effects-linked context exists.

### Lattice Forge

Lattice Forge candidate records SHOULD remain `candidate_not_admitted` until packaging, SBOM, signing, rollback tests, malformed-input tests, network posture, evidence contract validation, and accountability requirements are complete.

### Sherlock

Sherlock discovery records SHOULD expose:

- source freshness;
- runtime provenance;
- confidence;
- evidence refs;
- network/source posture tags;
- privacy and safety tier;
- accountability ledger refs when present.

## Non-goals

The following are explicitly out of scope for execution:

- autonomous weapon tasking;
- target selection;
- target engagement;
- evasion guidance;
- bypassing communications restrictions;
- unauthorized tracking;
- precision restoration for sensitive locations without policy authorization;
- executing any effects-linked workflow without authority, policy, evidence, and audit.

## Acceptance criteria

The platform can claim first-pass conformance when:

1. every live-capable runtime boundary includes network resilience and accountability sections;
2. runtime evidence bundles include network posture and secret posture;
3. Lattice candidate validation fails if a candidate lacks safety boundary or remaining admission requirements;
4. Agentplane refuses execution candidates that lack evidence/replay metadata;
5. SocioSphere can validate standards compliance and source-governance requirements;
6. Sherlock exposes provenance and freshness in discovery records;
7. no runtime is admitted to production solely from a fixture proof;
8. defense/public-safety and effects-linked contexts produce accountability ledger refs before production use.
