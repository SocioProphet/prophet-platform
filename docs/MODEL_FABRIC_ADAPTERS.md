# Model Fabric Adapter Contracts

Prophet Platform uses model-fabric adapter contracts to describe how platform services bind to the first model-fabric backing tools.

## Scope

The first adapter set covers:

- `model-router`
- `guardrail-fabric`
- `model-governance-ledger`
- `agent-registry`

These are contract fixtures only. They define service refs, command refs, input/output refs, evidence refs, policy refs, and explicit boundaries.

## Boundary

The first adapter contract set is deterministic and local-only.

It does not:

- call external providers;
- execute model inference;
- mutate model-governance ledgers;
- grant agent authority;
- store secret material;
- write model artifacts.

SourceOS remains carry-only. It can carry clients, refs, launchers, cache policy, and evidence collectors. It must not promote models or replace service artifacts.

## Validation

The contract fixture lives at:

```text
contracts/model-fabric/runtime-adapter-set.example.json
```

The validator lives at:

```text
apps/lattice-studio/src/lattice_studio/model_fabric_adapters.py
```

The test suite validates required surfaces, boundaries, service refs, and failure cases.
