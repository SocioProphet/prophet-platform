# Fog Stack SVF / Signadot parity lane

Status: contract and productization directive

## Purpose

This document defines the Fog Stack SVF lane for Signadot-style service virtualization and agent validation without overstating current runtime parity.

The comparison target is not general enterprise agent architecture. The comparison target is the narrow but important live validation loop that Signadot has productized: per-change Kubernetes sandboxes, request routing, baseline-environment fallback, deterministic validation jobs, MCP-facing agent interaction, and PR-readiness evidence.

Fog Stack should answer that lane directly, but the architecture must remain ours: policy-bound, receipt-backed, replayable, AgentPlane-linked, PolicyPlane-linked, and compatible with the existing release/trust/runtime evidence graph.

## Positioning

McKinsey / QuantumBlack are ahead mostly in public packaging and consulting narrative.

Signadot is ahead in one productionized runtime lane: live Kubernetes sandbox/service-virtualization UX for developer and coding-agent validation.

Prophet Platform / Fog Stack is already ahead in the trust and release plane. The current Fog Stack parity path proves local, CI-backed, non-mutating, evidence-based operator proof across release, registry, deploy, GitOps, runtime dry-run, Agent Machine node evidence, immutable/declarative update readiness, AgentPlane linkage, and PolicyPlane linkage.

The product gap is therefore precise:

```text
Fog Stack trust/release/runtime evidence graph: strong
Fog Stack live SVF request-routing and sandbox execution: not production-complete
Signadot live SVF product lane: strong
Signadot governed release/evidence/trust operating substrate: not our architecture
```

## Claim boundary

This document does not claim Signadot vendor parity.

This document does not claim production Kubernetes sandbox execution.

This document does not authorize live cluster mutation.

This document does not replace the existing `make fogstack-parity-readiness` posture. Current Fog Stack parity remains bounded to local, contract-backed, non-mutating, CI-proven evidence until live cluster apply, external signing identity, production observability, network registry publication, live AgentPlane execution, and GitOps controller reconciliation receipts are implemented.

## Required SVF object model

Fog Stack SVF should introduce a small contract family instead of hard-coding any vendor:

- `SandboxLease` — the bounded execution lease for one change set, agent run, or PR.
- `BaselineEnvironmentRef` — the shared environment used for unchanged dependencies.
- `ChangedServiceSet` — the changed workloads, resources, images, branches, or patches.
- `RoutingKeyHash` — the request-routing selector, stored as a digest or scoped reference rather than an uncontrolled raw secret.
- `ContextPropagationProfile` — required HTTP/gRPC/message propagation rules.
- `MeshRoutingPlan` — routing mechanism and target mesh, such as Istio, Linkerd, DevMesh, gateway routing, or local simulation.
- `ValidationJobPlan` — deterministic validation jobs, test commands, fixtures, timeouts, retries, and required artifacts.
- `ValidationRunReceipt` — signed or verifiable run output proving what executed and which evidence was observed.
- `PolicyDecisionRef` — PolicyPlane decision allowing, denying, or requiring review for the lease.
- `AgentPlaneRunRef` — AgentPlane execution context or replay reference.
- `GitOpsReconciliationRef` — GitOps controller or generated bundle reconciliation evidence.
- `RollbackProofRef` — proof that the lease was torn down or that rollback is available.

## Backend strategy

Fog Stack SVF must be backend-neutral.

Supported backend modes should be:

1. `local_dry_run` — current non-mutating local evidence path.
2. `sociosphere_svf` — Sociosphere-owned SVF execution and receipt authority.
3. `signadot_adapter` — optional adapter to consume or orchestrate Signadot-style sandbox evidence.
4. `mesh_native_adapter` — future in-house Kubernetes service-mesh implementation.
5. `external_receipt_import` — import mode for third-party validation receipts.

No backend may bypass PolicyPlane or AgentPlane receipt linkage.

## Signadot adapter contract

The Signadot adapter is not the architecture. It is one backend implementation behind the Fog Stack SVF contract.

A Signadot adapter is acceptable only when it can produce or import evidence for:

- sandbox lease identity,
- baseline environment reference,
- changed service set,
- routing key hash,
- routing/context propagation profile,
- validation job plan,
- validation run outcome,
- teardown or expiry evidence,
- policy decision reference,
- AgentPlane run reference,
- artifact digest set,
- non-claims for unsupported guarantees.

The adapter must fail closed when any of the following are missing for a blocking readiness decision:

- verified receipt,
- policy decision reference,
- current change digest,
- routing isolation evidence,
- validation job outcome,
- teardown or expiry proof,
- non-production boundary when running outside a production-approved profile.

## Product-pack impact

Fog Stack SVF should be tracked as a sub-lane under Fog Stack Automation / Workflow and Fog Stack Access until it has an independent lifecycle.

Near-term pack status:

- `Fog Stack Access` keeps the customer-facing proof path.
- `Fog Stack Automation / Workflow` owns the agent validation workflow lane.
- `Fog Stack Security / Trust` owns policy, receipt, signing, and non-claim enforcement.
- `Fog Stack Runtime / Agent Machine Node Ops` owns node substrate and execution evidence.

Do not split a separate repository yet. The trust/release/runtime graph is still the dominant shared substrate.

## MVP acceptance criteria

The first credible Fog Stack SVF MVP is complete when the repository can prove the following without manual side channels:

1. A change set produces an `SVFValidationRequest` with repo, ref, paths, actor, and change digest.
2. PolicyPlane returns an explicit allow, deny, or require-review decision.
3. AgentPlane owns the execution or imports a verifiable external receipt.
4. A backend produces a `SandboxLease` or equivalent lease record.
5. Routing evidence is present, even for local dry-run mode.
6. Validation jobs emit deterministic outcome records.
7. Teardown, expiry, or rollback evidence is recorded.
8. The receipt binds change digest, sandbox lease, validation jobs, artifacts, policy decision, AgentPlane run, and non-claims.
9. PR readiness is blocked unless the observed evidence state meets the required evidence state.
10. The operator can run one command and receive a machine-readable readiness record.

## Competitive answer

The correct public statement is:

```text
Signadot proves the market wants live agent validation sandboxes.
Fog Stack generalizes that pattern into a governed validation fabric: service virtualization plus release evidence, policy admission, AgentPlane replay, runtime receipts, SourceOS/Agent Machine substrate, and IBM-style operator proof.
```

That is the line that lets us respect the real product gap without conceding the platform architecture.

## Immediate implementation plan

1. Preserve existing `validate-svf-agent-contract` and `validate-live-sociosphere-svf-contract` as non-vendor SVF controls.
2. Add a Fog Stack SVF adapter-readiness fixture that models Signadot-style evidence without claiming vendor parity.
3. Add a validator that rejects any fixture claiming production readiness or vendor parity without live evidence.
4. Add the SVF lane to Fog Stack pack status as a productization sub-lane, not a split repo.
5. Wire the resulting validator into the Fog Stack parity readiness path only after the fixture and negative controls are stable.
