# DevSecOps Workroom Report v0.1

Report: `report:workroom:devsecops:post-merge:scope-d-example`
Workroom: `workroom:devsecops:post-merge:scope-d-example`

## Event

| Field | Value |
| --- | --- |
| Lane | post_merge_incident |
| Runtime parity level | contract_only |
| Incident | incident://pagerduty/scope-d-example/INC-1001 |
| Event type | production_incident |
| Status | investigating |
| Decision state | needs_review |
| Summary | Fixture incident reports elevated 5xx responses after deployment of changed service. |

## Evidence

| Type | Evidence ref | Producer | Summary |
| --- | --- | --- | --- |
| metric_observation | evidence://observability/scope-d-example/5xx-spike | Fixture observability connector | Synthetic telemetry reports 5xx rate above threshold for the API service after deploy window. |
| deployment_metadata | evidence://deployment/scope-d-example/recent-deploy | Fixture deployment connector | Synthetic deployment metadata records changed-service deploy within the incident time window. |
| topology_snapshot | evidence://gaia/topology/scope-d-example/blast-radius | GAIA topology fixture | Topology fixture links API service to checkout and account frontends as potential blast-radius consumers. |

## RCA Claims

| Status | Confidence | Claim | Statement |
| --- | --- | --- | --- |
| observation | high | rca-claim:scope-d-example:5xx-observation | The fixture observed elevated 5xx responses for the API service after the deploy window. |
| supported_causal_claim | medium | rca-claim:scope-d-example:recent-deploy-supported | The recent changed-service deploy is a supported candidate cause for the fixture 5xx spike, pending counterevidence review. |

## GAIA Blast Radius

| Field | Value |
| --- | --- |
| Topology ref | topology://gaia/workroom/scope-d-example/post-merge |
| Blast-radius ref | blast-radius://gaia/workroom/scope-d-example/INC-1001 |
| Radius status | supported_by_topology |
| Affected nodes | service://scope-d/api |
| Candidate consumers | frontend://scope-d/checkout, frontend://scope-d/account |
| Confidence | medium |

Impact hypotheses:
- If the API service is degraded, checkout and account frontends are plausible consumers affected by the incident window.

## Action Grants

| Action class | Status | Approval required | Grant | Scope |
| --- | --- | --- | --- | --- |
| read_only | allowed | False | action-grant:scope-d-example:read-incident-evidence | Read fixture incident evidence and topology refs. |
| production_change | requires_human_approval | True | action-grant:scope-d-example:rollback-production | Rollback production deployment for API service. |

## Guardrail Decision Bindings

| Grant | Guardrail fixture | Expected decision | Binding status |
| --- | --- | --- | --- |
| action-grant:scope-d-example:read-incident-evidence | guardrail-fixture:devsecops-workroom:safe-read-only-probe | allow | aligned |
| action-grant:scope-d-example:rollback-production | guardrail-fixture:devsecops-workroom:unsafe-mutation-without-grant | deny | requires_review |

## Remediation

| Risk | Status | Plan | Summary |
| --- | --- | --- | --- |
| high | candidate | remediation-plan:scope-d-example:rollback-candidate | Consider production rollback only after human review and counterevidence check. |

## Regression Fixtures

| Status | Fixture | Target validation plan | Summary |
| --- | --- | --- | --- |
| candidate | regression-fixture:scope-d-example:post-deploy-5xx-guard | validation-plan://scope-d-example/post-deploy-5xx-guard | Create pre-merge validation plan candidate that fails when changed-service route produces 5xx-class responses under checkout/account traffic fixture. |

## Non-claims

- Report is generated from fixture records only.
- Report does not execute infrastructure.
- Report does not inspect production systems.
- Report does not confirm RCA causality.
- Report does not authorize remediation.
- Report does not certify Signadot feature parity.
