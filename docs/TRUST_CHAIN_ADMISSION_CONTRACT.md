# Prophet Trust Chain admission contract

Status: v0.1 contract specification
Owner repo: `SocioProphet/prophet-platform`
Parent standard: `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
Implementation tracker: `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`

## Purpose

This document defines the first Prophet Platform contract surface for Prophet Trust Chain: `admit_artifact`.

`admit_artifact` is the platform-facing product/API contract that composes external and internal evidence into a governed admission decision for a requested artifact and scope.

The contract is intentionally evidence-reference-first. It does not embed scanner output, SBOM contents, full policy bundles, model factsheets, or execution receipts directly. It records stable references to those authorities so the platform can compose a decision while preserving source ownership.

## Scope

The first tranche supports the `RuntimeAsset` path because it is the cleanest bridge to the Lightwell-class open-source security pattern:

```text
RuntimeAsset
  -> SBOM / VEX / lockfile / signature / scan record
  -> policy profile
  -> AgentPlane validation / replay
  -> Guardrail decision
  -> admission decision
```

The broader standard later composes additional artifact types:

- `BootReleaseSet`
- `SourceArtifact`
- `PackageArtifact`
- `ModelArtifact`
- `DatasetArtifact`
- `AgentArtifact`
- `ToolArtifact`
- `WorkflowArtifact`

## Fixture files

The initial fixtures live under `contracts/trust-chain/`:

- `admit-artifact-request.example.json`
- `admit-artifact-response.allowed.example.json`
- `admit-artifact-response.denied.example.json`

The validator is:

- `tools/validate_trust_chain_contracts.py`

Run locally:

```bash
make validate-trust-chain-contracts
```

## Request contract

The request fixture contains:

- `schema_version`: contract schema version, currently `0.1`.
- `request_id`: stable request identifier with the prefix `trust-chain:admit-artifact-request:`.
- `requested_decision`: requested decision mode, such as `preview_admission`, `production_admission`, or `runtime_validation`.
- `requested_scope`: environment, tenant, workspace, and risk tier.
- `artifact`: artifact type, artifact ref, optional source ref, and digest.
- `evidence_refs`: references to external or internal evidence authorities.
- `requested_checks`: named checks requested by the caller.
- `non_claims`: explicit boundaries preventing fixture or contract overclaiming.

## Response contract

The response fixture contains:

- `schema_version`: contract schema version, currently `0.1`.
- `request_id`: originating request identifier.
- `response_id`: stable response identifier with the prefix `trust-chain:admit-artifact-response:`.
- `status`: currently `admission_decided` for decision-bearing responses.
- `decision`: one of the canonical decision states.
- `decision_scope`: environment, tenant, workspace, and risk tier for which the decision applies.
- `artifact`: artifact identity and digest.
- `posture`: normalized source, package, runtime, vulnerability, patch, policy, AgentPlane, and promotion posture.
- `evidence_refs`: source-owned evidence references supporting the decision.
- `remediation`: required remediation instructions when denied, quarantined, or escalated.
- `warnings`: decision warnings.
- `non_claims`: explicit boundaries preventing overclaiming.

## Decision states

The initial validator accepts the canonical Prophet Trust Chain decision states:

- `allow`: all required evidence is present and acceptable for the requested scope.
- `deny`: an invariant failed or policy disallows the requested use.
- `escalate`: human or higher-authority review is required.
- `quarantine`: artifact or action must be isolated until repaired or revoked.
- `allow_with_context`: use is allowed with explicit constraints or compensating controls.
- `provisional`: temporary or lower-trust admission with expiration, telemetry, or review obligations.

## Required request evidence for v0.1

The first validator requires request evidence keys for the `RuntimeAsset` path:

- `sbom_ref`
- `vex_ref`
- `lockfile_ref`
- `signature_ref`
- `scan_record_ref`
- `policy_profile_ref`

The request can include additional refs, such as:

- `agentplane_validation_ref`
- `model_governance_ref`
- `guardrail_decision_ref`
- `runtime_receipt_ref`

## Required response posture for v0.1

The first validator requires these posture keys:

- `source_posture`
- `package_posture`
- `runtime_posture`
- `vulnerability_posture`
- `patch_posture`
- `policy_posture`
- `agentplane_posture`
- `promotion_posture`

These fields are normalized summaries. They are not substitutes for the underlying evidence refs.

## Allow invariant

An `allow` response must satisfy:

- no remediation steps;
- no warnings;
- `policy_posture` equals `satisfied`;
- `agentplane_posture` equals `validated`;
- at least one evidence ref exists;
- the decision scope is explicit.

The current allowed fixture is scoped to preview and does not claim production certification.

## Deny / quarantine invariant

A `deny` or `quarantine` response must satisfy:

- remediation steps are present;
- warnings are present;
- policy posture is `failed` or `blocked`;
- every remediation step has an authority;
- every remediation step is marked `required_before_admission`.

The current denied fixture proves fail-closed behavior for regulated-enterprise production admission when package/runtime posture is blocked and verified replay is missing.

## Authority boundaries

The platform contract composes evidence but does not own every evidence source.

Authority ownership:

- `SocioProphet/lattice-forge`: runtime/package/build evidence.
- `SourceOS-Linux/sourceos-boot`: boot, recovery, rollback, and device verification evidence.
- `SocioProphet/policy-fabric`: policy profile, exception, patch SLA, break-glass, and certification policy.
- `SocioProphet/guardrail-fabric`: runtime and action admission decisions.
- `SocioProphet/agentplane`: validation, replay, run, promotion, reversal, and receipt evidence.
- `SocioProphet/model-governance-ledger`: model, adapter, dataset, eval, promotion, rollback, and revocation evidence.
- `SocioProphet/agent-registry`: agent identity, capabilities, tool rights, and revocation posture.
- `SocioProphet/model-router`: model/provider routing evidence.
- `SocioProphet/sherlock-search`: retrieval and operator inspection of evidence records.
- `SocioProphet/sociosphere` and `SocioProphet/prophet-workspace`: review, workroom, workflow, and user-facing surfaces.

## Non-goals

This contract does not claim:

- IBM/Red Hat Lightwell integration;
- live vulnerability scanning;
- production certification from fixtures alone;
- replacement of SPDX, CycloneDX, OSV, Sigstore, SLSA, in-toto, cloud scanners, GitHub evidence, or external clearinghouse evidence;
- runtime mutation from UI, search, or workroom surfaces;
- model promotion without evaluation receipts and runtime/package evidence.

## Next contract slices

The next platform-side contract slices should be:

1. `admit_workflow`: compose RuntimeAsset, ModelArtifact, DatasetArtifact, AgentArtifact, ToolArtifact, and WorkflowArtifact evidence.
2. `request_exception`: route a blocked or review-required admission into Policy Fabric and Sociosphere review workflow.
3. `record_remediation`: bind repair execution evidence from AgentPlane to the original denied admission response.
4. `revoke_admission`: record trust withdrawal, rollback, deactivation, or revocation after new evidence invalidates an earlier admission.
