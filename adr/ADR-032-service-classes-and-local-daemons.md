# ADR-032: Service classes and local daemons in prophet-platform

## Status
Proposed

## Context
`prophet-platform` is the runtime home for platform apps and deployment wiring, but not every
platform app is a Kubernetes service. The current repo already carries cluster-facing components
(`apps/api`, `apps/gateway`, `apps/socioprophet-web`) and infrastructure manifests, but adjacent
repos include at least one clearly local/runtime-bound daemon: Lampstand, a GNOME/Linux desktop
indexing + search service with an explicit daemon boundary, local SQLite/FTS5 storage, and
user-session runtime paths.

Forcing every runtime into the cluster shape would distort packaging, security boundaries, and
operator expectations.

## Decision
We formalize four service classes inside `prophet-platform`:

1. **edge service**: browser-facing HTTP/WebSocket entry points (for example `gateway`)
2. **cluster service**: internal networked runtimes deployed via K8s or similar
3. **local daemon**: per-host or per-user services deployed via distro packaging, systemd user
   units, launch agents, or equivalent
4. **contract/standards input**: non-runtime standards repos consumed by pinning and generation

Lampstand is classified as a **local daemon** for its first platform integration phase.

## Consequences
- `apps/lampstand/` belongs in the platform repo as a runtime service package.
- Lampstand should not get Argo/K8s manifests in its first integration wave.
- Platform docs and validation must stop assuming every `apps/*` entry is cluster-deployed.
- Receipts, contracts, and transport standards still apply to local daemons.
