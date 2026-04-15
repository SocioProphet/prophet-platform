# Next Gen TOM RACI v2

This document defines the corrected v2 operating model for the 30 capabilities in the deck. It preserves the five-domain structure while making central versus federated placement, accountability, and exception authority explicit.

## Canonical operating shape

- Engage: primarily federated into business towers
- Orchestrate: mixed; central standards plus federated execution
- Provision: primarily centralized as the shared brokerage and fulfillment factory
- Service: mixed; central operational disciplines with federated service ownership
- Control: centralized coalition authority for finance, security, audit, EA, sourcing, HR, and PMO

## Governance bodies

| Body | Purpose | Chair |
|---|---|---|
| Technology Portfolio Council (TPC) | Portfolio prioritization, tower demand alignment, and journey steering | CIO |
| Architecture & Brokerage Board (ABB) | Architecture patterns, service blueprints, provider integration patterns, and provisioning standards | CTO / Chief Architect |
| Technology Control Council (TCC) | Policy authority, exceptions, economics, security, audit, sourcing, and EA governance | CIO or COO |

## Domain ownership summary

| Domain | Default placement | Accountable authority |
|---|---|---|
| Engage | Federated into business towers | Tower CIO / business technology head |
| Orchestrate | Mixed; central methods plus domain execution | CTO / Chief Architect |
| Provision | Central shared factory | Head of Platform & Brokerage |
| Service | Mixed; central operational disciplines with federated service owners | Head of Service Operations |
| Control | Centralized control coalition | TCC |

## Capability summary by domain

### Engage
- Strategy
- Product Introduction and Change
- Demand Management
- Data Management and Analytics
- User Support and Help Desk
- Talent Retention

### Orchestrate
- Architecture and Design
- Release Development
- Release Testing
- Configuration Management
- Release Deployment
- API Management

### Provision
- Environment Provisioning
- Database and Data Provisioning
- Capacity Management
- Service Integration and Brokerage
- Availability
- Talent Management and Training

### Service
- Service Level Management
- Sourcing and Vendor Management
- Performance Management
- API Monitoring
- Problem and Incident Management
- Business Continuity

### Control
- Cost Planning
- Cost Control
- Project Office and Change
- Security Control
- Audit and Compliance
- Assets Management

## Key decision-rights rules

1. Engage cannot route demand directly to providers; it must route through Orchestrate and Provision.
2. Orchestrate cannot release a new path without a blueprint-ready fulfillment route.
3. Provision cannot fulfill a service that lacks policy attachment.
4. Service cannot onboard a runtime without owner, observability, continuity, and escalation metadata.
5. Control cannot impose policy that has no implementable hook in Orchestrate, Provision, or Service.
6. No exception is valid unless it has owner, rationale, compensating controls, expiry, and review date.
7. Every active service instance must have a cost center and asset/service record.
8. Every production service must have a named tower-facing owner even if it runs on shared services.

## Exception authority pattern

- Architectural and blueprint deviations: ABB
- Policy, provider, security, economics, or audit deviations: TCC
- Business-priority tradeoffs: TPC
- Major incident operational deviations: Head of Service Operations under established incident authority
