# Next Gen TOM Brokerage Architecture Binding

## Purpose

This document binds the normative Next Gen operating model to `prophet-platform` runtime concerns.

The platform role is to realize brokered service consumption through:
- standard resource models
- controlled fulfillment workflows
- evidence and cost metadata
- lifecycle guards and validation helpers

## Six-plane model

| Plane | Runtime concern |
|---|---|
| Experience | request intake, service catalog, API boundary |
| Control | policy decisions, approvals, cost and compliance rules |
| Fulfillment | service blueprints, workflows, provider adapters |
| Service | observability, SLM, incident and continuity hooks |
| Evidence | service-instance registration, control records, audit packages |
| Economics | usage, allocation, showback and unit-cost telemetry |

## Canonical objects carried in this repo

- `ServiceRequest`
- `ServiceInstance`
- `EventEnvelope`

These are starter objects only. They are sufficient to define the initial API, examples, and validation path.

## Control gates

- no fulfillment without a blueprint and policy decision
- no active service without registration and owner assignment
- no benefit credit without governed request flow and automated evidence capture

## Repo role

`prophet-platform` is the implementation binding for the operating model, not the sole canonical home of the standard.
