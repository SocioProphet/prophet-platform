# ProviderBinding Evidence Profile and Evidence Surfaces

## Purpose

This document maps `ProviderBinding.evidence_profile_id` and related profile references to existing platform evidence surfaces.

ProviderBinding declares which evidence profile applies. It does **not** itself store all evidence artifacts. Evidence is produced and stored by runtime lanes such as FogStack, PolicyPlane decision records, and AgentPlane execution bundles. The broker uses those upstream records to satisfy the evidence profile and justify approval.

## ProviderBinding fields that matter

The ProviderBinding contract includes profile references that drive broker approval and portability posture:

- `evidence_profile_id`: selects the evidence profile that defines required evidence kinds for the binding.
- `cost_meter_profile_id`: selects the cost metering profile.
- `continuity_profile_id`: selects the continuity profile.
- `exit_plan_ref`: points to the exit plan artifact.

See `specs/brokerage/schemas/provider-binding.schema.json` for the authoritative field list.

## Evidence profiles

Evidence profiles are machine-readable requirements for a binding.

- Schema: `specs/brokerage/schemas/provider-binding-evidence-profile.schema.json`
- Example: `specs/brokerage/events/examples/provider-binding-evidence-profile.example.json`

An evidence profile specifies the required evidence kinds for a given `(service_class, provider_class)` pairing and the minimum portability tier it can justify.

## Evidence surfaces by lane

The broker should satisfy evidence profiles using existing upstream artifacts.

| Lane | Existing artifact | Path | How it satisfies evidence profiles |
|---|---|---|---|
| FogStack live preflight | `FogStackLiveClusterPreflightRecord` | `schemas/runtime/fogstack-live-cluster-preflight-record-v0.1.schema.json` | proves read-only safety posture on real clusters: no mutation, no live apply, human approval required |
| FogStack runtime dry run | `FogStackRuntimeDryRunRecord` | `schemas/runtime/fogstack-runtime-dry-run-record-v0.1.schema.json` | proves AgentPlane linkage, PolicyPlane linkage, dry-run execution posture, and runtime policy context |
| PolicyPlane broker decision | `BrokerPolicyDecision` | `policy-fabric/contracts/schemas/broker-policy-decision.schema.json` | proves allow/deny/exception/review posture and carries `required_evidence_refs` |
| AgentPlane broker execution | `BrokerExecutionBundle` | `agentplane/schemas/broker-execution-bundle.schema.v0.1.json` | proves validation/smoke/replay bundle shape and carries `evidenceRefs` |
| Identity subject | `IdentitySubjectContext` | `contracts/identity/IdentitySubjectContext.v0.1.json` | proves subject class, tenant context, assurance posture, and policy linkage |
| Identity session | `IdentitySessionContext` | `contracts/identity/IdentitySessionContext.v0.1.json` | proves session-bound context and step-up/risk state when required |
| Identity proof ingress | `IdentityProofIngressRecord` | `contracts/identity/IdentityProofIngressRecord.v0.1.json` | proves accepted, rejected, or inconclusive proof ingress and evidence linkage |
| Office runtime | `office_*` records | `schemas/office/*.schema.json` | proves document, writeback, side-effect policy, or adapter posture when the service class is office/document mediated |

## Where evidence references live

Evidence references should live in the evidence-producing artifacts:

- `BrokerPolicyDecision.required_evidence_refs` in PolicyPlane.
- `BrokerExecutionBundle.evidenceRefs` in AgentPlane.
- FogStack artifact refs and digests in runtime readiness and dry-run records.

When the broker needs a normalized view, it should wrap those references into an EvidencePack or ProviderBindingApprovalRecord rather than duplicating FogStack, AgentPlane, or PolicyPlane content.

## Recommended evidence ref pattern

When a normalized EvidencePack is introduced, use stable refs with explicit kind prefixes. Examples:

```text
fogstack-live-preflight://fogstack.access.live-cluster-preflight.record.json
fogstack-runtime-dry-run://fogstack.access.runtime-dry-run.record.json
policy-decision://broker/decision-standard-app-env-001
agentplane-bundle://bundle-provider-binding-smoke-001
identity-subject://subject/demo-operator
identity-session://session/demo-session
identity-proof://proof/demo-proof
```

## Approval rule

A ProviderBinding can move to `Approved` only when:

1. its `evidence_profile_id` requirements are satisfied by upstream evidence artifacts, or
2. an explicit exception record exists with owner, rationale, compensating controls, expiry, and review date.

## Runtime posture

The broker must reference current runtime evidence instead of creating parallel broker evidence records. New broker evidence objects should be introduced only when the evidence alignment map identifies a real gap.
