# FogStack → Sherlock → Prophet Integration

## Purpose

This document normalizes the recovered FogStack design work into the Sherlock and Prophet Platform body plan so we can integrate it without collapsing repo or service boundaries.

## High-value FogStack contributions

### 1. Environment and fog ontology
FogStack contributes the missing physical and operational object model:

- site
- zone
- room
- node
- interface
- radio
- sensor
- trust domain
- node group
- topology edge
- risk zone
- device model
- device instance
- twin state
- flow
- interference event
- deployment profile

### 2. Artifact and promotion spine
FogStack contributes an OCI-centered release and provenance grammar:

- artifact records
- digest identity
- SBOM references
- provenance references
- signature state
- promotion lanes
- compatibility metadata
- deployment-profile compatibility

### 3. Environment dashboard grammar
FogStack contributes a strong operator-facing page model:

- Overview
- Physical Map
- Logical Topology
- Cluster / Edge Ops
- Devices / Telemetry
- RF / EMF / Network
- Security / Posture
- AI / Pipelines / Models
- Planner / What-if
- Artifact / Release Browser

### 4. Identity as prime plane
The identity-plane work contributes the constitutional doctrine that identity, capability, delegation, attestation, and revocation cut across all planes and must not be treated as auxiliary metadata.

## What this fixes in Sherlock

FogStack fills the following gaps:

- environment deep-dive semantics
- physical / edge / fog topology ontology
- artifact / provenance / promotion evidence model
- dashboard surface grammar
- deployment profile taxonomy
- identity-plane constitutional doctrine

## Normalized ontology additions

Add these canonical objects to Sherlock and Prophet runtime contracts:

- site
- zone
- room
- node
- interface
- radio
- sensor
- trust_domain
- node_group
- topology_edge
- risk_zone
- device_model
- device_instance
- twin_state
- flow
- interference_event
- artifact
- provenance_record
- promotion_event
- deployment_profile
- principal
- capability
- delegation_contract
- attestation
- revocation

## New deep-dive modes

Sherlock should support these deep-dive modes:

- repo deep dive
- environment deep dive
- artifact / release deep dive
- room / control-plane deep dive
- case deep dive

## Hosting implications for Prophet Platform

Prophet Platform should host:

- Topology Environment Service
- Artifact Release Service
- Identity Policy Service
- Dashboard BFF and dashboard shell
- Deep-Dive Orchestrator
- Search Evidence Service
- Evaluation Tournament Service
- Case Triage Service

## Boundary corrections

Do not merge FogStack wholesale into `sherlock-search`.

Only import there:
- evidence schemas
- artifact / environment evidence objects
- deep-dive contracts
- corpus and benchmark patterns

Keep adjacent lanes distinct:
- environment / topology lane
- artifact / provenance lane
- search / evidence lane
- shell / control-plane lane
- cases / action lane

## Immediate normalization tasks

1. Convert FogStack docs into canonical runtime schemas.
2. Extend the Sherlock ontology pack.
3. Extend deep-dive report schemas.
4. Add deployment-profile support to Prophet Platform hosting plans.
5. Add artifact and environment evidence sources to evaluation corpora.
6. Keep source-repo boundaries clean while hosting all services through Prophet Platform.
