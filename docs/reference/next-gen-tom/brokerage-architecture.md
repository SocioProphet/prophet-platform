# Brokerage Reference Architecture v2

## Purpose

The brokerage architecture is the kernel that turns a hybrid-cloud operating model into ITaaS. It standardizes service consumption, fulfillment, control, evidence, and economics across internal services, private cloud, public cloud, SaaS, partner services, and legacy estates.

## Six-plane model

| Plane | Purpose | Primary owner |
|---|---|---|
| Experience plane | Intake, catalog, self-serve UX/API, tower-facing request paths | Engage |
| Control plane | Identity, approvals, policy decisions, exceptions, economics and compliance rules | Control |
| Fulfillment plane | Orchestration, service blueprints, provider adapters, provisioning and deployment workflows | Provision |
| Service plane | Runtime operations, observability, SLM, incident/problem, continuity, vendor/service monitoring | Service |
| Evidence plane | Evidence capture, asset/service graph, approvals, audit packages, lineage and control records | Control with Service/Provision producers |
| Economics plane | Usage metering, cost allocation, showback/chargeback, unit economics, budget status | Control |

## Canonical objects

- `ServiceOffering`
- `ServiceBlueprint`
- `ProviderProfile`
- `ServiceRequest`
- `PolicyDecision`
- `ServiceInstance`
- `EvidencePack`
- `CostMeter`
- `ExceptionRecord`
- `ContinuityRecord`

## Policy hooks

1. Identity and entitlement hook
2. Service-class eligibility hook
3. Provider eligibility hook
4. Architecture conformance hook
5. Data and jurisdiction hook
6. Continuity and resilience hook
7. Economics and budget hook
8. Separation-of-duties hook
9. Exception expiry hook
10. Retirement closure hook

## Non-negotiable control gates

- No provisioning without a blueprint.
- No blueprint without policy attachment.
- No live instance without registration.
- No registration without owner and cost center.
- No production onboarding without observability and incident routing.
- No exception without explicit expiry and accountable owner.
- No retirement without evidence closure and meter closure.
