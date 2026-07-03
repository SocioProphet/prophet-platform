# Repo Governance MVP

## Purpose

This lane provides the minimum Prophet Platform substrate required to lift Sociosphere repo-governance observations into governed findings and policy-review requests without coupling Sociosphere to a local-only governance engine.

This MVP intentionally stops before deployment infrastructure, cloud provisioning, cluster orchestration, or live mutation execution.

## MVP flow

1. Sociosphere emits typed repo-governance observations.
2. Prophet Platform ingests the observation packet.
3. The MVP runner groups observations by repository.
4. Rule findings are emitted.
5. Findings requiring governance review become policy-request packets.
6. No repository mutation occurs.

## Current contracts

### Observation contract

`contracts/repo-governance/repo-governance-observation.v0.schema.json`

Carries:
- provenance;
- parser identity;
- extraction method;
- confidence level;
- temporal validity;
- evidence digest.

### Finding contract

`contracts/repo-governance/repo-governance-finding.v0.schema.json`

Carries:
- rule ID;
- antecedent observations;
- blockers;
- policy-review requirement;
- non-authorizing action status.

### Policy-request contract

`contracts/repo-governance/repo-governance-policy-request.v0.schema.json`

Carries:
- requested governance decision;
- finding linkage;
- policy-review-ready state.

## Safety boundary

This MVP is advisory and governance-oriented only.

It does not:
- mutate repositories;
- execute workflows;
- apply GitOps changes;
- authorize deployment;
- authorize cluster mutation;
- provision cloud resources.

All findings remain advisory until a future policy-fabric decision layer explicitly authorizes a bounded action candidate.

## Current demonstration

The MVP currently demonstrates:
- active-spine governance observations from Sociosphere;
- promotion-ready findings for `SocioProphet/hellgraph`;
- stale corpus-loop review findings;
- policy-review request emission.

## Next platform tranche

The next tranche should add:
- RDF named-graph lifting;
- replayable rule-evaluation records;
- policy-decision packets;
- ledger-ready governance audit records;
- adapter replacement for RDF-native graph traversal.

## Explicit stop boundary

This work intentionally stops before:
- GCP provisioning;
- Kubernetes deployment;
- Argo CD wiring;
- runtime action execution;
- cluster reconciliation;
- hosted policy services.
