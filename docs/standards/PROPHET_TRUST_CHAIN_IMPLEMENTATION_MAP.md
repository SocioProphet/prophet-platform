# Prophet Trust Chain implementation map

Status: active cross-repo tranche map
Owner repo: `SocioProphet/prophet-platform`
Parent standard: `docs/standards/PROPHET_TRUST_CHAIN_V0.md`

## Purpose

This document records the implementation state for Prophet Trust Chain across the SocioProphet, SourceOS, and workspace repositories.

Prophet Trust Chain maps the platform to the Lightwell-class enterprise open-source security pattern while extending it into governed enterprise AI admission. The standard treats open-source package/runtime evidence as one required lane inside a broader evidence system covering boot, package, runtime, model, dataset, agent, tool, workflow, policy, execution, receipt, remediation, rollback, revocation, and learning.

## Current platform baseline

The platform baseline is no longer only a prose standard. It now includes:

- `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
- `contracts/trust-chain/admit-artifact-request.example.json`
- `contracts/trust-chain/admit-artifact-response.allowed.example.json`
- `contracts/trust-chain/admit-artifact-response.denied.example.json`
- `tools/validate_trust_chain_contracts.py`
- `Makefile` target `validate-trust-chain-contracts`
- README discoverability and validation guidance

## Canonical evidence spine

The minimum Lightwell-compatible evidence spine is:

```text
RuntimeAsset
  -> SBOM / lockfile / signature / scan record
  -> VulnerabilityFinding
  -> PatchCandidate
  -> PatchValidation
  -> PolicyDecision
  -> AdmissionDecision
  -> AgentPlane RunArtifact / ReplayArtifact
  -> RuntimeReceipt
  -> PromotionRecord or RevocationRecord
```

The broader Prophet Trust Chain path is:

```text
BootReleaseSet + RuntimeAsset + ModelArtifact + DatasetArtifact + AgentArtifact + ToolArtifact + WorkflowArtifact
  -> composed policy evaluation
  -> governed admission
  -> execution receipt
  -> repair / rollback / revocation / learning
```

## Repository implementation map

| Repo | Role | Issue / status | Required first slice |
|---|---|---:|---|
| `SocioProphet/prophet-platform` | Product/API composition, platform standard, contract fixtures, validation | landed | Standard map, `admit_artifact` fixtures, validator, Makefile target, README entrypoint. |
| `SocioProphet/lattice-forge` | Runtime/package/build provenance | `#17` | Extend `RuntimeAsset` with SBOM, VEX, lockfile digest, provenance, signature/attestation, scan, vulnerability posture, patch posture, trust tier, promotion and rollback/revocation evidence. |
| `SocioProphet/policy-fabric` | Policy-as-code and exception governance | `#92` | Dependency admission, package-risk exceptions, patch SLA, AI-framework risk class, runtime promotion, break-glass, production certification policy. |
| `SocioProphet/guardrail-fabric` | Runtime enforcement and action admission | `#34` | Consume trust-chain evidence before effectful action; fail closed for missing, stale, or blocked evidence. |
| `SocioProphet/agentplane` | Validated execution, replay, receipts | `#261` | Add supply-chain validation evidence linking SBOM, VEX, lockfile, signature, scan, policy, guardrail, validation, replay, and runtime receipt. |
| `SocioProphet/model-governance-ledger` | Model/data/eval/factsheet/promotion evidence | `#25` | Bind model promotion and factsheets to runtime/package trust-chain evidence. |
| `SourceOS-Linux/sourceos-boot` | Boot, recovery, rollback, device verification | `#25` | Emit boot/device verification evidence for BootReleaseSet, manifest hash, boot mode, release set, device claim, verification result, rollback/recovery posture. |
| `SocioProphet/agent-registry` | Agent identity, capability, tool rights | `#46` | Bind agent manifests to admitted tools, model routes, datasets, memory scopes, runtime classes, policy/admission refs, revocation/downgrade posture. |
| `SocioProphet/model-router` | Model/provider routing under policy | `#18` | Route only through admitted or review-gated model/runtime/provider evidence; emit allow, downgrade, fallback, deny, or review decisions. |
| `SocioProphet/sherlock-search` | Evidence retrieval and operator inspection | `#62` | Index admission responses, posture fields, evidence refs, remediation steps, and receipt refs for provenance-preserving queries. |
| `SocioProphet/sociosphere` | Workroom coordination, review, exception, repair workflows | `#438` | Surface trust-chain admission state in workrooms and professional workrooms without becoming the admission authority. |
| `SocioProphet/prophet-workspace` | Workspace UX/product contract | `#19` | Expose trust-chain admission status, posture summary, evidence refs, remediation/review actions, and linked Sociosphere workflow refs. |

## Execution order

The recommended order is dependency-first, then enforcement, then surfaces:

1. `lattice-forge#17` and `policy-fabric#92`.
2. `guardrail-fabric#34`.
3. `agentplane#261`.
4. `model-governance-ledger#25`, `agent-registry#46`, and `model-router#18`.
5. `sourceos-boot#25` in parallel, because it extends admission downward into boot/device trust.
6. `sherlock-search#62`, `sociosphere#438`, and `prophet-workspace#19` for evidence discovery and operator/workroom surfaces.

## Acceptance boundary

A repo slice is not complete until it provides:

- a machine-readable contract, schema, or fixture;
- at least one allowed or valid example;
- at least one denied, blocked, invalid, or review-required example where applicable;
- validator, test, or CI coverage;
- explicit boundary language avoiding overclaiming;
- a reference back to `SocioProphet/prophet-platform/docs/standards/PROPHET_TRUST_CHAIN_V0.md`.

## Non-claims

This map does not claim:

- IBM/Red Hat Lightwell integration;
- live vulnerability scanning;
- production certification from fixtures alone;
- replacement of SPDX, CycloneDX, OSV, Sigstore, SLSA, in-toto, cloud scanners, GitHub evidence, or external clearinghouse evidence;
- runtime mutation from UI, search, or workroom surfaces;
- model promotion without evaluation receipts and runtime evidence.

## Product posture

IBM/Red Hat-style systems secure the open-source substrate.

Prophet Trust Chain governs the intelligent enterprise that runs on top of that substrate.

The intended posture is to consume Red Hat/Lightwell-class evidence, GitHub evidence, OSV evidence, Sigstore/SLSA/in-toto evidence, cloud scanner evidence, internal CI evidence, model-governance evidence, and AgentPlane execution receipts, then convert them into governed enterprise AI admission and action.
