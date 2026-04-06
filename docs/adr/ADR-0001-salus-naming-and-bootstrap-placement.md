# ADR-0001: Name the medical program SocioProphet Salus and bootstrap it inside prophet-platform

## Status

Proposed bootstrap decision.

## Context

We need a stable umbrella name and an immediate landing zone for medical-platform work. The desired outcome is a dedicated repository family, but the available chat connector can currently create branches, files, and pull requests in existing repositories; it cannot create a brand-new GitHub repository directly from this session.

The medical program spans multiple layers:

- patient-facing agent workflows
- professional intelligence
- policy and trust
- interoperability
- schemas and contracts
- platform execution and evidence

That makes a temporary placement inside the existing platform repository operationally reasonable as a bootstrap, provided we preserve a clean extraction path.

## Decision

We name the umbrella medical program **SocioProphet Salus**.

We use the doctrine line **Salus Omnium**.

We reserve the following subsystem names:

- Cura — patient-facing care agent
- Ars Medica — professional workspace
- Evidentia — evidence layer
- Arca Salutis — vault and consent substrate
- Aegis — policy and trust layer

We bootstrap the work under `SocioProphet/prophet-platform` in a dedicated `docs/verticals/salus/` namespace plus related `rpc/` and `schemas/` stubs until a dedicated repository can be created.

## Consequences

Positive:

- immediate staging inside an existing maintained repository
- architectural alignment with platform, contracts, and policy
- clean review path through a draft PR
- straightforward future extraction into `socioprophet-salus`

Negative:

- temporary placement may blur the eventual repository boundary
- implementation code and program-definition docs may cohabit longer than ideal if extraction is delayed

## Follow-up

- create dedicated repository when a repo-creation path is available
- preserve file layout compatibility for lift-and-shift extraction
- add a second ADR when the extraction is executed
