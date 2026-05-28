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
make smoke-health
```

## Reading order

1. `docs/ARCHITECTURE.md`
2. `docs/TRITRPC_SPEC.md`
3. `docs/TRITRPC_PLATFORM_BINDING.md`
4. `docs/PLATFORM_EVAL_FABRIC.md`
5. `docs/SVF_VALIDATE_CHANGE_AGENT_CONTRACT.md`
6. `contracts/`
7. `infra/k8s/`

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
