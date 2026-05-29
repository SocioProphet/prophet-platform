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
make validate-adversarial-scenario-ref
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `docs/PLATFORM_EVAL_FABRIC.md`
5. `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
6. `docs/ADVERSARIAL_SCENARIO_PLATFORM_BINDING.md`
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

## Adversarial scenario references

Prophet Platform carries a narrow reference-only binding for governed SCOPE-D adversarial scenarios. This contract allows the platform to reference upstream scenario artifacts without creating a scenario builder, operator UI, runtime executor, report exporter, live collector, or memory writeback path.

Relevant files:

- `docs/ADVERSARIAL_SCENARIO_PLATFORM_BINDING.md`
- `contracts/security/adversarial-scenario-ref.schema.json`
- `contracts/security/adversarial-scenario-ref.example.json`
- `tools/validate_adversarial_scenario_ref.py`

Validate locally:

```bash
make validate-adversarial-scenario-ref
```

Boundary: scenario references are evidence-bearing pointers only. They do not grant runtime execution, procedure execution authority, engagement authorization, downstream activation, live target access, credential access, payload delivery, state mutation, destructive behavior, external delivery, report export, claim promotion, or memory writeback.

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
