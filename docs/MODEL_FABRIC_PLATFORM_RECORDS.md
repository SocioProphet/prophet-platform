# Model Fabric Platform Records

Prophet Platform projects model-fabric service registry entries into the canonical `PlatformAssetRecord` spine.

## Scope

The first model-fabric record emitter reads the functional service registry and emits records for:

- `model-router`
- `guardrail-fabric`
- `model-governance-ledger`
- `agent-registry`

It does not invoke model providers, route requests, evaluate guardrails, mutate ledgers, or grant agent authority. It only projects registry metadata into platform records.

## SourceOS carry boundary

Every emitted model-fabric record requires SourceOS carry policy to remain `carry-only`:

- SourceOS may carry clients, launchers, refs, cache policy, and evidence collectors.
- SourceOS must not promote models.
- SourceOS must not replace service artifacts.

## Integration

The records are emitted by `apps/lattice-studio/src/lattice_studio/model_fabric_records.py` and tested against `contracts/modality/functional-service-registry.v1.example.json`.
