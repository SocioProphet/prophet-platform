# Operating Cadence and KPI Model v1

This document maps the operating model to measurable management rhythms, evidence rhythms, journey-facing metrics, and benefits realization signals.

## Cadence design principles

- Use the shortest cadence that matches the operational half-life of the capability.
- Continuous telemetry should replace manual status reporting wherever possible.
- Journey-facing metrics must stay separate from internal-only activity metrics.
- Benefits are only credited when manual paths are materially displaced.

## Domain cadence model

### Engage
- Weekly demand triage
- Biweekly product and release intake
- Monthly portfolio review
- Quarterly strategy and workforce review

Primary KPI families:
- demand-to-commit lead time
- feature or service adoption
- user satisfaction and help-desk deflection
- journey investment coverage and priority alignment

### Orchestrate
- Weekly design and release-methods review
- Sprint / release cadence for testing and deployment
- Monthly standards and lifecycle review

Primary KPI families:
- deployment frequency
- change lead time
- automated test share
- config drift rate
- managed API coverage

### Provision
- Daily provisioning watch
- Weekly capacity and provider-onboarding review
- Monthly service and resilience review
- Quarterly skills review

Primary KPI families:
- environment lead time
- self-service provisioning rate
- standardized blueprint usage
- provider onboarding time
- uptime and latency against platform SLOs

### Service
- Daily incident and operational watch
- Weekly service and problem review
- Monthly SLM, vendor, continuity, and performance review
- Quarterly resilience exercise

Primary KPI families:
- journey outage minutes
- mean time to detect / restore
- SLO attainment
- monitored API coverage
- vendor support quality for journey-critical services

### Control
- Weekly exception and transformation governance watch
- Monthly cost, risk, and control review
- Quarterly audit-readiness and planning cycle
- Annual formal attestation where required

Primary KPI families:
- policy-by-default coverage
- chargeback/showback completeness
- evidence-pack readiness
- registered-instance coverage
- unit-cost trend on journey-critical services

## Core enterprise KPI stack

| Layer | KPI family | Examples |
|---|---|---|
| TOM layer | Flow, standardization, control by default | provisioning lead time, automated deployment rate, policy-by-default coverage, registered-instance coverage |
| Business-unit layer | Demand and delivery | demand-to-commit lead time, product introduction cycle time, service portfolio throughput |
| Customer-engagement layer | Experience and service quality | first-contact resolution, feature adoption, service satisfaction |
| Journey layer | End-to-end customer outcomes | onboarding completion time, abandonment rate, straight-through processing rate, journey uptime |

## Benefit realization rule

A capability only gets economic credit when the new path has displaced the old path. Evidence should include new-path volume share, retired manual steps, reduced exception or rework rate, and runtime or cost telemetry that proves the operating change persisted beyond a pilot window.
