# cloud-twin

**Cloud-Twin as a Service** on the Prophet Platform. Submit a `GenesisSeed`, get a
verified Twin whose K3 lifecycle is a replayable `TwinEventEnvelope` stream.

Read-only / no-op skeleton (Cybernetic Agentic Genesis & Inception plan, Phase-1
exit criteria: *a seed becomes a verified twin end to end; a no-op adapter
executes; replay reconstructs the lifecycle*). World-changing actuation
(AdapterDescriptor with dry-run + rollback) is gated behind later phases.

Contracts are the canonical schemas in `SourceOS-Linux/sourceos-spec`
(`GenesisSeed`, `TwinEventEnvelope`), vendored under `schemas/` for validation.

## API
- `GET  /health`
- `POST /twins` — body: a GenesisSeed → 201 `{twin_id, state, events}` (422 on a bad seed, fail closed)
- `GET  /twins/{twin_id}` — twin state + seed + events
- `GET  /twins/{twin_id}/events` — the replayable TwinEventEnvelope stream

## Run
```
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```

Deployed via GitOps: `deploy/values/cloud-twin.yaml` + the `cloud-twin` element in
`deploy/argocd/platform-services.yaml` (shared `charts/socioprophet-service`).
