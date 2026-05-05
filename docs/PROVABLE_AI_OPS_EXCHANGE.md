# Provable AI Operations Exchange

Status: draft v0.1
Owner lane: Prophet Platform runtime and evidence fabric
Primary intent: replace analyst-authority intelligence with certified, reproducible, chain-of-custody operating intelligence for agentic enterprise operations.

## Thesis

The legacy analyst model sells conclusions, reputation, and periodic research distribution. The SocioProphet replacement model sells verifiable operating intelligence: claims backed by signed artifacts, reproducible evaluation runs, specialist attestations, policy decisions, custody events, and operational outcomes.

This is not a market-research feature. It is a control-plane pattern for enterprise AI operations.

## What changes

A normal analyst brief says: trust the analyst.

A Provable Intelligence Brief says: here is the claim, here is the evidence, here are the artifacts, here is the benchmark pack, here are the model and agent runs, here are the policies that admitted or denied the work, here are the human and agent reviewers, here is the custody chain, here are the uncertainty bounds, and here is how to reproduce or challenge the result.

## Non-goals

- Do not create a detached analyst-content shop.
- Do not publish unsupported conclusions as first-class platform artifacts.
- Do not let a human specialist, model, or agent certify work outside its scoped credential.
- Do not treat PDF, slide, or dashboard renders as the system of record.
- Do not accept evidence whose origin, hash, license, and custody trail are unknown.

## Canonical loop

1. Intake a question, market signal, operational issue, benchmark target, or governance concern.
2. Register the work as a scoped exchange or brief.
3. Collect evidence with source, hash, license, quality, and custody metadata.
4. Produce or update artifacts: benchmark packs, eval suites, model cards, policy bundles, agent manifests, dashboards, reports, ontologies, or playbooks.
5. Run policy admission before analysis, agent execution, publication, or deployment.
6. Execute agent and specialist work under AgentPlane custody.
7. Record model, tool, prompt, dataset, notebook, policy, and runtime versions.
8. Generate claims only from evidence-linked outputs.
9. Attach specialist and peer-review attestations.
10. Publish a Provable Intelligence Brief as a rendered view over the evidence graph.
11. Keep the brief live: expire, contest, supersede, retract, or recertify it as evidence changes.

## Trust model

The exchange uses four trust layers.

### Artifact trust

Every data product, eval suite, report render, policy bundle, model card, ontology, dashboard, or agent manifest has a stable artifact ID, version, content hash, schema reference, owner, license, status, and custody history.

### Specialist trust

A specialist may be a human, organization, service, or certified agent. Each credential has an issuer, subject, scope, assurance level, evidence references, status, expiration, and signature. Credentials are scoped and revocable.

### Action trust

Every agent or service action produces custody events. The required minimum is actor, tool/runtime/model reference, input references, output references, policy decision, start/finish timestamps, status, metrics, and signatures when available.

### Claim trust

A claim cannot be certified unless it has supporting evidence, artifact references, review attestations, policy decisions, confidence, and an expiry or recertification path. Counterevidence is first-class.

## Contract family

The v0.1 platform contract is materialized in:

- `contracts/ProvableAIOpsExchange.v0.1.json`

It defines:

- `Claim`
- `Evidence`
- `Artifact`
- `CustodyEvent`
- `SpecialistCredential`
- `AgentAction`
- `EvaluationRun`
- `BenchmarkPack`
- `PolicyDecision`
- `ReviewAttestation`
- `IntelligenceBrief`

This complements the existing `EvidenceReceipt` and event-envelope spine. `EvidenceReceipt` remains the small runtime receipt. `ProvableAIOpsExchange` is the higher-order graph envelope for assembled intelligence, certification, and operating proof.

## Product surfaces

### Sherlock Search

Sherlock discovers claims, evidence, artifacts, specialists, benchmark packs, policy decisions, briefs, counterclaims, and operational playbooks. Search result ranking should be able to prefer certified artifacts over unsupported prose.

### Sociosphere

Sociosphere is the registry and graph surface for public and internal artifact discovery. It owns relationship traversal across organizations, specialists, claims, evidence, custody events, agent capabilities, and trust state.

### AgentPlane

AgentPlane records action custody for agent and tool execution. It must emit `AgentAction`, `PolicyDecision`, `CustodyEvent`, and receipt references for every admitted action.

### Guardrail Fabric and Policy Fabric

The policy layer gates ingestion, analysis, agent execution, specialist review, certification, publication, deployment, rollback, revocation, and export.

### Model Governance Ledger

The ledger records model and model-router decisions, eval runs, model-card artifacts, risk approvals, benchmark outcomes, recertification events, and revocation records.

### DeliveryExcellence

DeliveryExcellence turns the evidence graph into operating metrics: cost, latency, cycle time, benchmark deltas, automation ROI, agent reliability, governance coverage, control failures, review burden, and delivery throughput.

### Ontogenesis

Ontogenesis is the schema generator and semantic compiler. It should promote this v0.1 JSON contract into JSON-LD, SHACL, Avro, TriTRPC IDL, and CRD shapes.

### HolographMe

HolographMe owns specialist identity, credential projection, scoped digital-twin boundaries, review history, conflicts, reputation, and revocation surfaces.

### Superconscious

Superconscious watches for stale briefs, weak claims, missing counterevidence, decaying benchmark coverage, recurrent agent failures, and recertification needs.

## Certification levels

### Level 0: Draft

The brief or artifact is visible but uncertified. It may contain unresolved evidence gaps.

### Level 1: Evidence-linked

Claims reference evidence and artifacts, but review and reproducibility are incomplete.

### Level 2: Reproducible

The benchmark, eval, notebook, or pipeline can be reproduced from registered artifacts and environment metadata.

### Level 3: Specialist-reviewed

Scoped human or agent specialists have signed review attestations.

### Level 4: Policy-certified

The work passed required governance, safety, licensing, privacy, export, and publication controls.

### Level 5: Operationally proven

The recommendation or automation has measured operating results and continuous telemetry.

## Minimum admissibility rules

A certified brief must have:

- At least one registered `IntelligenceBrief` artifact.
- At least one `Claim` with evidence references.
- At least one `Evidence` object per certified claim.
- At least one `CustodyEvent` for every certified artifact.
- A policy decision for publication or deployment.
- Review attestations for every scoped specialist claim.
- Confidence and expiry metadata for non-trivial claims.
- Explicit counterevidence handling.
- Reproduction instructions for benchmark- or eval-backed claims.
- Revocation and supersession path.

## Demo vertical slice

The first demo should replace a conventional enterprise AI analyst note.

Example: `Enterprise AI Automation Readiness and Agentic Ops Benchmark`.

The demo brief should contain:

1. Executive summary render.
2. Machine-readable claim graph.
3. Benchmark pack for automation maturity.
4. Evidence receipts for source material and benchmark outputs.
5. Model-router and agent execution logs.
6. Policy decisions for data admission and publication.
7. Specialist review attestations.
8. DeliveryExcellence dashboard metrics.
9. Sherlock discovery surface.
10. Sociosphere registry record.
11. Revocation and recertification hooks.

## Acceptance criteria for the v0.1 platform lane

- The contract validates as JSON Schema draft 2020-12.
- Platform docs explain how the exchange relates to EvidenceReceipt, eval fabric, knowledge-reason, Lampstand, semantic-bridge, and zone-router.
- At least one synthetic exchange bundle can be created without touching live customer data.
- The synthetic bundle contains one brief, three claims, five evidence records, two artifacts, one benchmark pack, one eval run, one policy decision, one agent action, one specialist credential, one review attestation, and custody events tying them together.
- The bundle can be rendered as a human-readable Provable Intelligence Brief.
- The same bundle can be queried by ID, artifact type, claim status, specialist scope, policy decision, benchmark pack, and custody subject.
- Failed or missing custody data blocks certification above Level 1.

## Implementation sequence

1. Materialize the v0.1 contract.
2. Add a synthetic fixture bundle.
3. Add a validation script for contract and fixture integrity.
4. Register the lane in the integration map.
5. Add read endpoints to the existing evidence or knowledge-reason surfaces.
6. Add write/admission events through AgentPlane once the contract is stable.
7. Promote schema generation into Ontogenesis.
8. Register artifacts and specialists in Sociosphere.
9. Attach model and eval records in Model Governance Ledger.
10. Publish the first Provable Intelligence Brief through Sherlock and SocioProphet docs.

## Operating doctrine

This lane exists to make enterprise intelligence challengeable, executable, inspectable, and governable. Analyst authority is replaced by artifact authority. Artifact authority is not blind trust; it is the combination of provenance, custody, reproducibility, policy, specialist review, and measured operational effect.
