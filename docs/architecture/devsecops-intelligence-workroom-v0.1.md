# DevSecOps Intelligence Workroom v0.1

Status: planning and implementation contract  
Plane: Prophet Platform product/API surface  
Related lanes: Sociosphere environment state, AgentPlane sandbox execution/evidence, Signadot-parity runtime lane, Aurora-style incident investigation

## Purpose

This document defines the first governed DevSecOps Intelligence Workroom capability.

The workroom unifies two lanes that must remain distinct in implementation:

1. **Pre-merge validation lane** — Signadot-style sandbox/runtime validation for PRs, changes, validation plans, route isolation, and observed execution evidence.
2. **Post-merge incident lane** — Aurora-style incident investigation for alerts, evidence gathering, topology/blast-radius analysis, RCA claims, remediation planning, postmortems, and regression fixture generation.

The product objective is not to clone either external pattern. The objective is to provide a governed intelligence loop:

```text
change_proposed
  -> sandbox_requested
  -> validation_run_observed
  -> merge_decision
  -> deploy_observed
  -> incident_detected
  -> investigation_run
  -> evidence_backed_rca_claims
  -> remediation_plan
  -> postmortem_lesson
  -> regression_fixture
  -> future_validation_plan
```

## Dependency boundary

The Signadot-parity lane is an active dependency with moving runtime implementation state. This workroom must not hard-code the current partial runtime state as final parity.

Current estate boundary:

- Sociosphere owns workspace and environment state, environment profile registry, environment request state, and observed/missing/stale environment readouts.
- AgentPlane owns execution records, sandbox run records, replay records, evidence artifacts, receipts, and validation run evidence.
- Prophet Platform owns the product/API invocation surface and workroom orchestration over Sociosphere and AgentPlane.
- ProCybernetica owns authority semantics and policy primitives.
- SourceOS / Agent Machine owns local runtime substrate and local-to-cluster bridge contracts.
- GAIA owns operational topology and environment/world-evidence projection.
- Ontogenesis owns typed semantics and schema/ontology discipline.
- Alexandrian Academy owns lesson promotion and canonization.
- SCOPE-D owns adversarial validation of the DevSecOps/AIOps agent loop.

The workroom must bind to the sandbox runtime through stable contracts, not through assumptions about a specific runtime implementation.

## Non-negotiable non-claims

This v0.1 plan does not certify Signadot feature parity.

This v0.1 plan does not claim live sandbox execution until observed runtime evidence satisfies the parity gates already recorded in the Sociosphere environment sandbox bridge plan.

This v0.1 plan does not authorize live infrastructure mutation.

This v0.1 plan does not collapse validation failures and production incidents into one undifferentiated incident type.

This v0.1 plan does not allow an agent to execute privileged actions without an explicit action grant and policy evaluation.

## External pattern absorption

### Signadot-style lane

The workroom consumes the pre-merge validation pattern:

- PR-scoped environment lifecycle;
- changed-service-only deploy path;
- baseline fallback path;
- HTTP/gRPC route isolation;
- async queue/topic isolation;
- stateful resource isolation;
- validation job execution evidence;
- teardown and TTL evidence;
- policy, secret, and data-boundary enforcement;
- agent-facing invocation surface.

In v0.1, the workroom may operate against contract-only or synthetic runtime evidence. Any user-facing parity label must disclose the runtime parity level.

### Aurora-style lane

The workroom absorbs the post-merge incident investigation pattern:

- alert or incident event ingestion;
- bounded agent investigation;
- cloud, Kubernetes, log, docs, runbook, topology, and repo evidence gathering;
- structured RCA claim generation;
- impact and blast-radius estimation;
- remediation plan proposal;
- optional code-fix proposal;
- postmortem lesson generation;
- regression fixture generation.

In v0.1, post-merge investigation may operate on fixtures and bounded connectors. It must not present fluent RCA prose without typed evidence references.

## Core object model

The following objects define the workroom contract:

- `ChangeSet`
- `EnvironmentRequest`
- `SandboxEnvironment`
- `ValidationPlan`
- `ValidationRunReceipt`
- `BehavioralDivergenceEvent`
- `IncidentEvent`
- `InvestigationRunReceipt`
- `ToolProbe`
- `EvidencePacket`
- `RCAClaim`
- `BlastRadiusEstimate`
- `RemediationPlan`
- `ActionGrant`
- `HumanDecision`
- `PostmortemLesson`
- `RegressionFixture`
- `CanonPromotionCandidate`

## BehavioralDivergenceEvent

A `BehavioralDivergenceEvent` is the umbrella object for a system behavior deviation.

Allowed subtypes:

- `pre_merge_validation_failure`
- `sandbox_regression`
- `contract_violation`
- `performance_regression`
- `security_policy_regression`
- `production_incident`
- `post_deploy_degradation`
- `customer_impact_event`

The event must carry:

- source lane: `pre_merge_validation` or `post_merge_incident`;
- repo/workspace reference when available;
- change/deploy reference when available;
- environment reference;
- topology reference when available;
- evidence references;
- claim references;
- decision state;
- non-claims.

## RCA claim discipline

`RCAClaim` must distinguish the following statuses:

- `observation`
- `hypothesis`
- `supported_causal_claim`
- `confirmed_causal_claim`
- `falsified_claim`
- `unknown`

No claim may be upgraded from `hypothesis` to `supported_causal_claim` without evidence references.

No claim may be upgraded to `confirmed_causal_claim` without both supporting evidence and explicit counterevidence handling.

The UI and API must separate facts, hypotheses, recommendations, and actions.

## Action grant discipline

Every tool action must be classified before execution.

Action classes:

- `read_only`
- `diagnostic_mutation`
- `reversible_mitigation`
- `irreversible_mutation`
- `credential_sensitive`
- `data_sensitive`
- `customer_visible`
- `destructive`
- `privileged_identity`
- `network_exposure`
- `production_change`

Every non-read action requires an `ActionGrant`.

Every high-risk action requires explicit human approval unless a future policy document grants a narrow emergency exception.

Every credential-sensitive action requires separate policy handling and receipt capture.

## Workroom panes

The first UI/workroom surface should expose:

- timeline;
- change/deploy context;
- environment/sandbox context;
- topology/blast-radius graph;
- evidence stream;
- validation results;
- hypotheses and RCA claims;
- agent actions and action grants;
- remediation options;
- human decisions;
- postmortem and lesson output;
- generated regression fixtures.

## Minimal v0.1 slice

The smallest credible slice is:

1. Accept a `ChangeSet` or fixture incident.
2. Resolve or request a sandbox/environment state through the existing Sociosphere/AgentPlane contracts.
3. Emit or ingest a `ValidationRunReceipt` or `InvestigationRunReceipt`.
4. Produce a `BehavioralDivergenceEvent` when validation fails or an incident is simulated.
5. Attach evidence references.
6. Generate at least one typed `RCAClaim`.
7. Generate one `RegressionFixture` candidate.
8. Show the chain in a workroom report or API response.

## Tranche plan

### Tranche A — define the governed loop

Deliverables:

- this canonical plan;
- umbrella issue;
- repo placement map;
- child issue set.

### Tranche B — make the loop validatable

Deliverables:

- schemas for `BehavioralDivergenceEvent`, `EvidencePacket`, `RCAClaim`, `InvestigationRunReceipt`, `RemediationPlan`, `ActionGrant`, and `RegressionFixture`;
- fixtures for one pre-merge validation failure and one production incident;
- validator script and CI hook.

### Tranche C — integrate the pre-merge lane

Deliverables:

- adapter from existing `validate_change` / environment request semantics into the workroom object model;
- support for runtime parity levels: `contract_only`, `synthetic_observed`, `runtime_observed`;
- no hard-coded dependency on final Signadot runtime implementation.

### Tranche D — integrate the incident lane

Deliverables:

- fixture-driven incident ingestion;
- investigation receipt;
- evidence packet;
- topology/blast-radius reference;
- RCA claim set;
- remediation plan candidate;
- postmortem lesson candidate.

### Tranche E — enforce action safety

Deliverables:

- action class taxonomy;
- action grant schema;
- blocked mutation fixture;
- allowed read-only fixture;
- credential-sensitive fixture;
- prompt/log/runbook injection adversarial fixture.

### Tranche F — expose the workroom

Deliverables:

- API or report surface showing the unified chain;
- UI skeleton only after schema and fixture contracts are stable.

### Tranche G — close the learning loop

Deliverables:

- incident-to-regression fixture generation;
- regression fixture to validation plan candidate;
- Alexandrian Academy canonization handoff candidate.

## Implementation guardrails

- Do not start with connector sprawl.
- Do not start with UI before schemas and fixtures.
- Do not duplicate Sociosphere environment state.
- Do not duplicate AgentPlane runtime evidence.
- Do not bypass the active Signadot-parity lane.
- Do not claim parity until parity gates have observed evidence.
- Do not let generated RCA prose outrun evidence.

## First issue set

1. Prophet Platform: create workroom object model and fixture validators.
2. AgentPlane: expose runtime sandbox run receipts to the workroom as stable evidence refs.
3. Sociosphere: expose environment request and observed/failed/stale environment state to the workroom.
4. GAIA: define minimal operational topology reference for validation and incident contexts.
5. Ontogenesis: mirror the workroom object model into typed ontology/schema discipline.
6. SCOPE-D: add adversarial AIOps validation fixtures.
7. Alexandrian Academy: define postmortem lesson to regression fixture to canon promotion handoff.
