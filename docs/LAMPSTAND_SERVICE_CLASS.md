# Lampstand in prophet-platform

Lampstand is integrated as a **local daemon**. It indexes local files, stores metadata in a local SQLite + FTS5 database, exposes a small daemon RPC surface, and is designed for a GNOME/Linux distribution rather than a cluster runtime.

## Deployment mode
- first-class platform app under `apps/lampstand/`
- packaged and supervised locally (systemd user unit in this patch kit)
- storage routed through SocioProfit/SocioProphet storage env vars when available
- receipts emitted into the platform receipt/evidence path

## Not in this phase
- no Argo/K8s manifests
- no browser-facing ingress
- no claim that upstream Lampstand is already fully hardened
