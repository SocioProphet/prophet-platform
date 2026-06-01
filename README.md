# Prophet Platform (SocioProphet)

This repository is the **runtime and deployment hub** for the SocioProphet platform.

It is intentionally a **thin platform monorepo**:
- `apps/` contains deployable services (API, gateway, web portal, search/index daemons, execution services)
- `contracts/` contains platform-facing event, evidence, and receipt contracts consumed by runtime services
- `docs/` contains platform-level guidance (architecture, transport binding, security, roadmap)
- `infra/` contains deployment wiring (Kustomize, Argo CD appsets, namespaces, etc.)
- `tools/` contains validation and smoke-test helpers (`standards.lock.yaml` gates platform drift checks)
- `libs/` contains small shared runtime bindings that adapt pinned upstream standards into platform code

## Why this repo exists

Standards and governance stay in dedicated upstream repositories. `prophet-platform` is where those standards become running services, concrete deployment topologies, and platform contracts.

## Quickstart

```bash
make validate
make validate-workroom-update-contract
make validate-professional-intelligence-manifest
make validate-svf-agent-contract
make validate-environment-validate-change-v2
make validate-trust-chain-contracts
make validate-channel-runtime-gates
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `professional-intelligence.manifest.yaml`
5. `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`
6. `docs/PLATFORM_EVAL_FABRIC.md`
7. `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
8. `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
9. `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`
10. `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`
11. `contracts/`
12. `infra/k8s/`

## Professional Intelligence manifest

`professional-intelligence.manifest.yaml` is the platform-side cross-repo alignment manifest for Professional Intelligence OS. It records runtime/platform ownership while pointing to upstream product, workspace, policy, model, topic, memory, receipt, and estate-ledger authority surfaces.

The `workspaceOS` lane is currently `contract-aligned`: Professional Workroom schema, example, validator, Sociosphere topology, workspace-inventory overlay, and systems-learning receipt exist. This does not imply runtime implementation or demo readiness.

Relevant files:

- `professional-intelligence.manifest.yaml`
- `tools/validate_professional_intelligence_manifest.py`

Validate locally:

```bash
make validate-professional-intelligence-manifest
```

Boundary: contract alignment does not imply runtime implementation. Runtime implementation does not imply demo readiness without evidence and adoption telemetry. Prophet Workspace owns workroom product semantics; Prophet Platform owns runtime deployment and service composition.

## Workroom update contract

Prophet Platform now carries a minimal workroom update request/response contract lane for Professional Workroom substrate refs. This is a no-runtime, no-network contract layer: it validates the shape and boundary of a request to attach recovered-substrate refs to a workroom surface, but it does not mutate live workroom state.

Relevant files:

- `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`
- `contracts/workspace/workroom-update-request.example.json`
- `contracts/workspace/workroom-update-response.accepted.example.json`
- `contracts/workspace/workroom-update-response.invalid-runtime-mutation.example.json`
- `tools/validate_workroom_update_contract.py`

Validate locally:

```bash
make validate-workroom-update-contract
```

Boundary: `accepted_for_review` is not execution. The accepted-response fixture requires `runtimeMutationPerformed: false`; the invalid mutation fixture proves that `runtimeMutationPerformed: true` under `accepted_for_review` is rejected. Runtime implementation requires a separate platform service contract, persistence model, policy gate, receipt path, and the runtime prerequisites in `docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md`.

## Sovereign Validation Fabric agent contract

Prophet Platform owns the agent-facing `validate_change` contract for Sovereign Validation Fabric. The first tranche is read-only and selection-oriented: it validates request, selected-plan response, and PR-readiness summary fixtures without executing Actions, issuing receipts, or granting agent autonomy.

Relevant files:

- `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
- `contracts/svf/validate-change-request.example.json`
- `contracts/svf/validate-change-response.example.json`
- `contracts/svf/pr-readiness-summary.example.json`
- `tools/validate_svf_agent_contract.py`

Validate locally:

```bash
make validate-svf-agent-contract
```

## Environment validation / `validate_change` v2

Prophet Platform also carries the first environment-validation request surface for the Signadot-parity bridge. This is the product/runtime contract layer: it accepts a change, references Sociosphere workspace/environment state, requests AgentPlane synthetic execution, and returns environment status plus evidence references.

Relevant files:

- `contracts/environment/validate-change-v2-request.example.json`
- `contracts/environment/validate-change-v2-response.environment-requested.json`
- `contracts/environment/validate-change-v2-response.environment-observed.json`
- `contracts/environment/validate-change-v2-response.environment-failed.json`
- `tools/validate_environment_validate_change_v2.py`

Validate locally:

```bash
make validate-environment-validate-change-v2
```

Boundary: this is still a synthetic/no-network contract layer. It does not create live infrastructure, route traffic, isolate queues, isolate stateful resources, or certify Signadot-style runtime parity. AgentPlane owns execution/evidence. Sociosphere owns workspace/environment state. Prophet Platform owns this product/API invocation contract.

## Prophet Trust Chain

Prophet Platform now carries the cross-repo **Prophet Trust Chain v0** standard map, the implementation tracker, and the first platform-side `admit_artifact` contract fixtures.

Prophet Trust Chain maps SocioProphet to the Lightwell-class enterprise open-source security pattern while preserving our broader boundary: package and runtime evidence are necessary, but enterprise AI admission also requires model, dataset, agent, tool, workflow, policy, execution, receipt, remediation, rollback, revocation, and learning evidence.

Relevant files:

- `docs/standards/PROPHET_TRUST_CHAIN_V0.md`
- `docs/standards/PROPHET_TRUST_CHAIN_IMPLEMENTATION_MAP.md`
- `contracts/trust-chain/admit-artifact-request.example.json`
- `contracts/trust-chain/admit-artifact-response.allowed.example.json`
- `contracts/trust-chain/admit-artifact-response.denied.example.json`
- `tools/validate_trust_chain_contracts.py`

Validate locally:

```bash
make validate-trust-chain-contracts
```

Boundary: this is a platform contract and standard-map lane. It does not claim IBM/Red Hat Lightwell integration, live scanner integration, or production certification from fixtures alone. The allowed fixture is scoped evidence composition; the denied fixture proves fail-closed production-admission behavior when blocking risk or missing verified replay exists.

## Channel-governed runtime gates

Prophet Platform now carries the first runtime-gate contract for channel-conditioned observations. This is the platform-side consumer of ProCybernetica Reciprocal Channel Governance, Ontogenesis `rcg:`, Memory Mesh channel provenance write gates, Regis epistemic edge records, and HolographMe projection-loss profiles.

Relevant files:

- `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`
- `contracts/channel-governance/runtime-gate.candidate-memory.example.json`
- `contracts/channel-governance/runtime-gate.confirmed-memory.rejected.example.json`
- `tools/validate_channel_runtime_gates.py`

Validate locally:

```bash
make validate-channel-runtime-gates
```

The candidate-memory fixture is expected to pass. The confirmed-memory fixture is expected to fail semantically because an ASR-conditioned percept attempts a confirmed-memory sink that is disallowed by the advisory channel envelope and lacks required repair posture.

Boundary: this is a contract and validator lane only. It does not add production middleware, broker policy, database schema, or API endpoint behavior.

## Evaluation fabric lane

The platform also carries a first-class **evaluation, observability, and competition-intelligence lane**.

Start here:
- `docs/PLATFORM_EVAL_FABRIC.md`
- `docs/LOCAL_DEV_EVAL_FABRIC.md`
- `docs/EVAL_FABRIC_GOVERNANCE.md`
- `apps/eval-fabric-api/`
- `schemas/eval/`
- `infra/local/docker-compose.eval-fabric.yml`

This lane is platform responsibility, not a detached benchmark pack. It owns the container, datastore, schema, and API bootstrap for platform-level ranking, replay, and intelligence work.

## Notes on this phase

This phase removes the plaintext `PING/PONG` bootstrap path and replaces it with a minimal **TriTRPC v1** runtime binding for internal service health traffic. The upstream `SocioProphet/TriTRPC` repository remains the normative transport source of truth; this repository only defines the platform-specific stream binding and deployment profile around that standard.
