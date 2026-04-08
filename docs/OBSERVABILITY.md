# Observability

## Bootstrap signals

The current platform phase should expose enough signal to debug the first runtime slice:

- gateway `/health`
- API health route over TriTRPC v1
- canonical `EventEnvelope` artifacts
- canonical `EvidenceReceipt` artifacts
- local receipt catalog entries for Lampstand

## Near-term additions

- structured service logs
- receipt correlation IDs surfaced in gateway and service logs
- replay-friendly event/evidence inspection tooling
- explicit failure taxonomy for runtime services and local daemons
