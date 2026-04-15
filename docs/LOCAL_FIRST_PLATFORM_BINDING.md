# Local-First Platform Binding

Status: Draft  
Repository role: runtime and deployment binding for local-first execution, sync, and governed evidence

## Purpose

This document defines how the platform runtime binds the local-first desktop, sync, policy, and transport stack into deployable services.

`prophet-platform` is where the standards become running topology. This repository therefore owns the runtime interpretation of:

- local commit then async sync behavior
- governed decision execution
- receipts and evidence publication
- session placement execution
- health, replay, and rollback coordination

## Runtime responsibilities

The platform runtime SHOULD provide services or modules for:

- sync ingress and sync acknowledgement
- receipt emission and evidence persistence
- placement execution against local / fog / cloud targets
- policy enforcement hooks for capability, trust, and routing decisions
- replay and rollback orchestration
- evaluation fabric hooks for scoring, ranking, and intelligence loops

## Local-first write path

A conforming platform service SHOULD preserve this sequence:

1. accept a local mutation or mutation receipt
2. persist durable local or edge-near state
3. emit a mutation receipt
4. queue governed replication
5. publish replication outcome or divergence outcome
6. make replay and repair evidence queryable

No interactive workflow should require a central round trip before acknowledging a successful local write when local policy permits the action.

## Runtime surfaces

### A. Sync control surface

Responsible for:

- mutation queueing
- replication tracking
- divergence detection
- repair scheduling
- replay initiation

### B. Policy execution surface

Responsible for:

- calling Policy Fabric decision services or using validated policy bundles
- enforcing capability and placement outcomes
- preventing runtime execution that violates local-first trust posture

### C. Evidence surface

Responsible for:

- correlating receipts across transport, policy, and runtime layers
- storing execution receipts and validation reports
- supporting replayable queries over decisions and outcomes

### D. Evaluation fabric surface

Responsible for:

- measuring utility, abuse, concentration, and operational quality
- ensuring ranking or routing feedback loops are visible and governed

## Desktop and package runtime implications

Where Prophet Platform coordinates desktop or agentic application services, it SHOULD assume:

- contained execution by default
- explicit capability mediation rather than blanket host access
- multiple remote / mirror support for package and update flows
- package receipt and rollback evidence

## Cross-repository relationship

- `SocioProphet/TriTRPC` transports deterministic decision and mutation envelopes
- `SocioProphet/policy-fabric` defines capability, reputation, remote trust, and placement policy
- `SocioProphet/socioprophet-standards-storage` defines the governing standard
- `SocioProphet/synapseiq` enriches evidence and semantic telemetry
- `SourceOS-Linux/sourceos-spec` must carry the typed contract layer for these runtime objects

## Initial implementation backlog

1. Add runtime receipt contract examples under `contracts/`
2. Add sync / divergence / repair service scaffolds under `apps/`
3. Add a platform receipt index and replay query path
4. Add platform-side policy enforcement integration tests
5. Bind evaluation fabric metrics to concentration and utility telemetry
