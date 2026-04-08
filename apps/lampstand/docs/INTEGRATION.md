# Lampstand platform integration

## Service role
Lampstand provides local file indexing and query for desktop/workspace contexts.

## Storage
The upstream service already supports these env vars:
- `SOCIOPROFIT_DATA_HOME`
- `SOCIOPROFIT_STATE_HOME`
- `SOCIOPROFIT_RUNTIME_HOME`

The platform wrapper should preserve those env vars and add receipt directories under state.

## Transport
Short term:
- allow upstream `unixjson` fallback for local/dev
- keep wrapper transport-neutral

Longer term:
- use pinned platform TriTRPC v1 profile for production bindings

## Receipt policy
Every materially completed daemon action should emit:
- an `EventEnvelope`
- an `EvidenceReceipt`
- service-specific event contracts where useful (for example `CarrierIngested`)

## Packaging
Initial deployment target is a user-session systemd unit, not Kubernetes.
