# Architecture

- **Wire**: TritRPC over Unix Domain Sockets (UDS) as the default trust boundary inside a host or node.
- **Browser access**: via a small **gateway** that terminates HTTP(S)/WebSocket at the edge and relays requests over TritRPC to UDS. Keep this strictly scoped.
- **Portal**: Vue 3 + Vite. No React/Carbon; lightweight, component-first.
- **Kubernetes**: Kustomize bases + overlays; Argo CD manages desired state (app-of-apps).
- **Security**: AEAD framing, nonces, and replay guards are spec’d in `TRITRPC_SPEC.md`. The exemplar API runs plaintext for legibility and should be swapped for the library once you drop it in.

## Components
- `apps/api`: Long-lived UDS service. Today: `Health.Ping -> Pong` exemplar.
- `apps/gateway`: Optional HTTP bridge for browsers or cross-host ingress.
- `apps/socioprophet-web`: UI that calls `/health` on the gateway in dev.
