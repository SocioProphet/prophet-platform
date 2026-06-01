# Prophet Trust Chain v0

Status: draft standard map
Owner repo: `SocioProphet/prophet-platform`
Scope: cross-repo enterprise AI supply-chain, runtime-admission, and evidence standard

## Purpose

Prophet Trust Chain is the SocioProphet control-plane standard for governing enterprise AI systems from source artifact through package, runtime, model, dataset, agent, tool, workflow, admission, execution, receipt, remediation, rollback, and learning.

The standard is designed to map cleanly to the emerging IBM/Red Hat Lightwell pattern without becoming a clone of it.

Lightwell-class systems focus on open-source software security: inventory, vulnerability discovery, triage, validated fixes, patch delivery, lifecycle management, production confidence, and enterprise audit.

Prophet Trust Chain treats that as one required evidence lane inside a broader governed-intelligence fabric. Open-source package posture is necessary but not sufficient for enterprise AI production. Production admission also depends on runtime provenance, model lineage, dataset consent and boundaries, agent capability, tool authorization, memory context, policy posture, execution evidence, cost posture, and reversible remediation.

## Strategic boundary

Prophet Trust Chain does not claim to replace Red Hat, OSV, GitHub Advanced Security, Sigstore, SLSA, SPDX, CycloneDX, in-toto, cloud scanner output, or Lightwell-class clearinghouse evidence.

It defines the control-plane contract that can consume those evidence sources, normalize them, bind them to SocioProphet runtime and agent records, apply policy, emit an admission decision, and preserve an auditable receipt.

The governing thesis is:

```text
External trust evidence + internal runtime evidence + model/agent evidence + policy
  -> governed admission
  -> evidence-producing execution
  -> receipt, repair, rollback, revocation, and learning
```

## Canonical loop

```text
Inventory
  -> Observe
  -> Normalize
  -> Assess
  -> Govern
  -> Admit or Reject
  -> Execute
  -> Receipt
  -> Repair / Rollback / Revoke
  -> Learn
```

This loop aligns with the existing SocioProphet governed-intelligence loop:

```text
Observe -> Anchor -> Normalize -> Propose -> Explain -> Verify -> Govern -> Act -> Receipt -> Learn
```

## Core object model

The v0 object model defines the minimum common language across repos.

- `SourceArtifact`: repository, commit, source package, upstream reference, or imported source unit.
- `PackageArtifact`: resolved dependency, package release, container layer, library, or AI framework component.
- `RuntimeAsset`: reproducible runtime, image, kernel, notebook environment, Ray/Beam image, or package channel release.
- `BootReleaseSet`: boot/recovery/install/update release set with manifest and verification evidence.
- `ModelArtifact`: model, adapter, embedding model, reranker, or hosted-provider route.
- `DatasetArtifact`: dataset, feature table, benchmark corpus, prompt set, retrieval corpus, or consent-scoped data boundary.
- `AgentArtifact`: agent manifest, capability profile, execution boundary, tool rights, and identity binding.
- `ToolArtifact`: callable tool, API, local command surface, MCP tool, connector, or infrastructure mutation path.
- `WorkflowArtifact`: workroom flow, validation flow, deployment flow, repair plan, or agent bundle.
- `VulnerabilityFinding`: CVE, OSV advisory, scanner finding, exploitability signal, dependency risk, or policy finding.
- `PatchCandidate`: proposed remediation, version bump, configuration hardening, replacement package, or compensating control.
- `PatchValidation`: test result, replay result, synthetic execution, environment validation, or human review result.
- `AdmissionDecision`: allow, deny, escalate, quarantine, allow-with-context, or provisional decision.
- `ExceptionRecord`: approved deviation, break-glass, temporary SLA exception, compensating control, or risk acceptance.
- `PromotionRecord`: evidence-backed movement toward production use.
- `RuntimeReceipt`: tamper-evident record of what ran, where, under what policy, and with what evidence.
- `RevocationRecord`: withdrawal of trust, artifact deactivation, rollback, model removal, dataset deletion, or policy denial.
- `CertificationRecord`: composed evidence bundle indicating that an artifact or workflow is approved for a defined scope.

## Repository responsibility map

### `SocioProphet/prophet-platform`

Role: enterprise control plane and product/API composition surface.

Responsibilities:

- Own platform-facing `admit_artifact` and `validate_change` product contracts.
- Compose package, runtime, model, agent, tool, workflow, and policy posture into a single admission response.
- Bind evidence references to deployable services, gateway routes, environment validation, and control-plane UI.
- Maintain this standard map and cross-repo implementation status.

Initial contracts to add:

- `contracts/trust-chain/admit-artifact-request.example.json`
- `contracts/trust-chain/admit-artifact-response.allowed.example.json`
- `contracts/trust-chain/admit-artifact-response.denied.example.json`
- `tools/validate_trust_chain_contracts.py`

### `SocioProphet/lattice-forge`

Role: runtime, package, build, and provenance boundary.

Responsibilities:

- Extend `RuntimeAsset` with SBOM, VEX, lockfile digest, signature, scan records, patch state, source-channel trust, and promotion evidence.
- Produce signed runtime releases with reproducible build and dependency evidence.
- Preserve Nix, Conda-compatible, notebook, Ray, Beam, and package-channel evidence.

### `SourceOS-Linux/sourceos-boot`

Role: boot, recovery, rollback, and device verification boundary.

Responsibilities:

- Bind `BootReleaseSet` to manifest hash, boot mode, selected release set, verification result, device claim, and rollback posture.
- Emit boot/recovery evidence for platform admission.
- Preserve local-first device registration and later mesh replication evidence.

### `SocioProphet/policy-fabric`

Role: policy-as-code, compiled execution plans, validation reports, exception governance, and release-pack posture.

Responsibilities:

- Define policy profiles for dependency admission, vulnerable-package exception, patch SLA, AI-framework risk class, runtime promotion, break-glass, and production certification.
- Compile policy into executable plans consumed by Guardrail Fabric and Prophet Platform.
- Emit validation, replay, and release-pack records.

### `SocioProphet/guardrail-fabric`

Role: deterministic runtime enforcement and claim/action admission.

Responsibilities:

- Consume package, runtime, model, agent, tool, and policy evidence before effectful action.
- Fail closed when required evidence is absent, stale, or invalid.
- Emit `sourceos.guardrail.decision.v0.1`-compatible decisions for package, infrastructure, database, tool, model, and agent action classes.
- Provide decision states: allow, deny, escalate, quarantine, allow-with-context, and provisional.

### `SocioProphet/agentplane`

Role: governed execution, placement, replay, promotion, reversal, and receipt evidence.

Responsibilities:

- Bind trusted artifacts to bundles.
- Validate bundle evidence before execution.
- Emit validation, placement, run, replay, promotion, reversal, session, route, and receipt artifacts.
- Add supply-chain validation evidence linking SBOM, scan, patch, policy, promotion, and runtime execution.

### `SocioProphet/model-governance-ledger`

Role: model, dataset, eval, factsheet, compliance, promotion, rollback, and revocation ledger.

Responsibilities:

- Bind model and adapter factsheets to runtime/package evidence.
- Require dataset lineage, consent boundary, evaluation receipts, drift posture, and promotion evidence.
- Preserve inference traces, training-run records, drift events, learning events, revocation, and rollback records.
- Reject promotion when runtime dependency evidence is missing or policy-denied.

### `SocioProphet/agent-registry`

Role: agent manifest, capability, identity, and tool-right registration.

Responsibilities:

- Bind agents to allowed tools, models, datasets, memory scopes, runtime classes, and policy gates.
- Provide agent capability records consumed by Guardrail Fabric and AgentPlane.
- Preserve revocation and capability downgrade posture.

### `SocioProphet/model-router`

Role: governed model/provider routing under policy.

Responsibilities:

- Bind routing decisions to model factsheets, provider posture, cost limits, fallback policy, and evidence references.
- Deny or downgrade routes when model, provider, or runtime evidence fails admission.

### `SocioProphet/sherlock-search`

Role: evidence discovery, retrieval, and operator inspection.

Responsibilities:

- Index trust-chain records for package, runtime, model, agent, workflow, policy, and receipt evidence.
- Support operator questions such as: why was this allowed, what changed, what is vulnerable, what is stale, and what needs remediation.

### `SocioProphet/holmes`

Role: explanation and reasoning traces.

Responsibilities:

- Produce explanation traces for admission decisions, claim admission, and remediation recommendations.
- Keep raw model output separate from admitted truth.

### `SocioProphet/sociosphere` and `SocioProphet/prophet-workspace`

Role: workroom, professional-intelligence, workflow, claims, and admission coordination.

Responsibilities:

- Surface trust-chain state in workrooms and professional workrooms.
- Preserve claim/admission workflow boundaries.
- Coordinate human review, exception acceptance, and repair decisions.

## Minimum Lightwell-compatible evidence spine

The first implementation tranche should produce a minimal but complete evidence path:

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

This is the narrow bridge to the Lightwell-class standard.

The broader Prophet path extends the bridge:

```text
RuntimeAsset + ModelArtifact + DatasetArtifact + AgentArtifact + ToolArtifact + WorkflowArtifact
  -> composed policy evaluation
  -> governed admission
  -> execution receipt
  -> repair / rollback / revocation / learning
```

## Admission response requirements

A composed admission response must include:

- artifact identity and type;
- requested environment and scope;
- source, package, runtime, model, dataset, agent, tool, and workflow references where applicable;
- vulnerability posture;
- patch posture;
- SBOM/VEX/provenance references where applicable;
- policy decision references;
- guardrail decision references;
- execution or validation references;
- promotion, exception, rollback, or revocation posture;
- final decision;
- machine-readable remediation instructions when denied or escalated.

## Decision states

- `allow`: all required evidence is present and valid for the requested scope.
- `deny`: an invariant failed or a policy disallows the requested use.
- `escalate`: human review is required before production use.
- `quarantine`: artifact or action must be isolated until repaired or revoked.
- `allow_with_context`: use is allowed with explicit constraints, warnings, or compensating controls.
- `provisional`: temporary or lower-trust admission, usually with expiration and telemetry obligations.

## Non-goals for v0

- Do not claim IBM/Red Hat clearinghouse scale.
- Do not claim full package remediation automation.
- Do not claim production certification without executable evidence.
- Do not replace specialized scanners or provenance standards.
- Do not turn raw model output, public benchmark scores, or scanner output alone into admitted truth.

## Immediate implementation checklist

1. Add Prophet Platform trust-chain request/response contracts and validator.
2. Extend Lattice Forge `RuntimeAsset` evidence fields for SBOM, VEX, scan, signature, patch, and promotion posture.
3. Add Policy Fabric trust-chain policy profiles for dependency admission, exception handling, and production certification.
4. Add Guardrail Fabric action-admission examples consuming runtime/package evidence.
5. Add AgentPlane supply-chain validation evidence fixture linking SBOM, scan, patch, policy, and replay artifacts.
6. Add Model Governance Ledger linkage from model factsheets and inference traces to runtime/package evidence.
7. Add Sherlock evidence indexing plan for trust-chain records.

## Product statement

IBM/Red Hat-style systems secure the open-source substrate.

Prophet Trust Chain governs the intelligent enterprise that runs on top of that substrate.

The intended product posture is not to out-Red-Hat Red Hat. The intended posture is to consume Red Hat/Lightwell-class evidence, GitHub evidence, OSV evidence, Sigstore/SLSA/in-toto evidence, cloud scanner evidence, internal CI evidence, model-governance evidence, and AgentPlane execution receipts, then convert them into governed enterprise AI admission and action.
