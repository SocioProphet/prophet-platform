# Next Gen TOM Brokerage Architecture Binding

This document explains the runtime-facing binding of the Next Gen operating model inside `prophet-platform`.

## Platform role

The platform realizes brokered service consumption through:
- controlled request intake
- standard resource models
- fulfillment workflows and provider adapters
- service-instance registration
- evidence and cost metadata

## Runtime planes

- Experience: request intake and API boundary
- Control: policy decisions, approvals, cost and compliance rules
- Fulfillment: blueprints, workflows, provider adapters
- Service: observability, SLM, incident and continuity hooks
- Evidence: registration, control records, audit packages
- Economics: usage, allocation, showback and unit-cost telemetry

## Repo role

`prophet-platform` is the implementation binding for the operating model, not the sole canonical home of the standard.
