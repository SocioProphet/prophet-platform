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
make validate-svf-agent-contract
make validate-environment-validate-change-v2
make validate-channel-runtime-gates
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `docs/PLATFORM_EVAL_FABRIC.md`
5. `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
6. `docs/CHANNEL_GOVERNED_RUNTIME_GATES.md`
7. `contracts/`
8. `infra/k8s/`

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
