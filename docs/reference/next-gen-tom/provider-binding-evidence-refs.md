# ProviderBinding Evidence References

## Purpose

This document maps `ProviderBinding.evidence_refs` to existing platform evidence artifacts.

`prophet-platform` should not create parallel broker evidence records when current runtime, identity, office, PolicyPlane, or AgentPlane artifacts already prove the required fact. ProviderBinding should reference those records and use service-class evidence profiles to decide whether a binding is approvable.

## Evidence references by lane

| Lane | Existing artifact | Path | ProviderBinding use |
|---|---|---|---|
| FogStack live preflight | `FogStackLiveClusterPreflightRecord` | `schemas/runtime/fogstack-live-cluster-preflight-record-v0.1.schema.json` | prove read-only live preflight, no mutation, no live apply, human approval required |
| FogStack runtime dry run | `FogStackRuntimeDryRunRecord` | `schemas/runtime/fogstack-runtime-dry-run-record-v0.1.schema.json` | prove AgentPlane run linkage, PolicyPlane decision linkage, dry-run mode, no mutation, runtime policy |
| PolicyPlane broker decision | `BrokerPolicyDecision` | `policy-fabric/contracts/schemas/broker-policy-decision.schema.json` | prove allow/deny/exception/review posture for provider binding or request |
| AgentPlane broker execution | `BrokerExecutionBundle` | `agentplane/schemas/broker-execution-bundle.schema.v0.1.json` | prove validation/smoke/continuity/exit/cost-meter/evidence-completeness bundle shape |
| Identity subject | `IdentitySubjectContext` | `contracts/identity/IdentitySubjectContext.v0.1.json` | prove subject class, tenant, assurance context, and policy refs |
| Identity session | `IdentitySessionContext` | `contracts/identity/IdentitySessionContext.v0.1.json` | prove session context, assurance, step-up, and risk state |
| Identity proof ingress | `IdentityProofIngressRecord` | `contracts/identity/IdentityProofIngressRecord.v0.1.json` | prove accepted/rejected/inconclusive proof ingress and evidence refs |
| Office version | `office_version_record` | `schemas/office/office_version_record.schema.json` | prove document version lineage and open execution backend |
| Office writeback | `office_writeback_record` | `schemas/office/office_writeback_record.schema.json` | prove saveback/writeback behavior and receipt refs |
| Office policy decision | `office_policy_decision_record` | `schemas/office/office_policy_decision_record.schema.json` | prove office action policy decision and side-effect posture |
| Office adapter profile | `office_adapter_profile` | `schemas/office/office_adapter_profile.schema.json` | prove open runtime adapter or quarantined closed-provider migration/compat profile |

## ProviderBinding evidence reference pattern

Use stable refs with explicit kind prefixes. Examples:

```text
fogstack-live-preflight://fogstack.access.live-cluster-preflight.record.json
fogstack-runtime-dry-run://fogstack.access.runtime-dry-run.record.json
policy-decision://broker/decision-standard-app-env-001
agentplane-bundle://bundle-provider-binding-smoke-001
identity-subject://subject/demo-operator
identity-session://session/demo-session
identity-proof://proof/demo-proof
office-adapter-profile://office-adapter-profile-google-workspace-import
office-policy-decision://office-policy-decision-demo-0001
```

## Approval rule

ProviderBinding approval requires either:

1. all evidence refs required by its service-class evidence profile, or
2. an explicit exception record with owner, rationale, compensating controls, expiry, and review date.

## Runtime posture

The broker must reference current runtime evidence instead of duplicating it. New broker evidence records should be introduced only when the evidence alignment map identifies a real gap.
