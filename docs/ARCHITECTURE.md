# Architecture

## Runtime topology

- **Normative wire**: TriTRPC v1 from the upstream `SocioProphet/TriTRPC` standards repo.
- **Platform transport binding**: 4-byte big-endian frame length + 24-byte nonce + TriTRPC envelope bytes.
- **On-host / same-pod mode**: `unix://` endpoints are preferred when API and caller share a host boundary.
- **Cross-pod / cluster mode**: `tcp://` endpoints are used when services run in separate Kubernetes pods.
- **Browser access**: via a small HTTP gateway that terminates browser traffic and relays internally over TriTRPC.
- **Portal**: Vue 3 + Vite.
- **Kubernetes**: Kustomize bases + overlays; Argo CD manages desired state.

## Why the extra binding exists

The current stable TriTRPC v1 Go port computes AEAD tags over the envelope and accepts a 24-byte nonce out-of-band. The platform therefore needs a small, explicit stream binding so runtime services can exchange authenticated frames over UDS or TCP without inventing ad hoc framing per service.

## Bootstrap services in this phase

- `apps/api`: minimal TriTRPC v1 service that accepts `platform.health.v1 / Health.Ping.REQ` and returns `Health.Ping.RES`.
- `apps/gateway`: minimal HTTP edge that calls the internal health route over the platform TriTRPC binding.
- `apps/socioprophet-web`: browser shell that hits the gateway.

## Next service target

After the transport spine is green, the first high-value runtime import should still be `lampstand`, because it is bounded, concrete, and immediately useful as local search/index infrastructure.
