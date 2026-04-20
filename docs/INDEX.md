# Docs Index — Prophet Platform

> **New here?** Start with [ARCHITECTURE.md](ARCHITECTURE.md), then follow the reading order below.

---

## Reading order

1. [ARCHITECTURE.md](ARCHITECTURE.md) — components, trust boundaries, data flow
2. [SECURITY.md](SECURITY.md) — security notes and hardening checklist
3. [SECURITY-MODEL.md](SECURITY-MODEL.md) — full threat model and AEAD details
4. [DEPLOYMENT.md](DEPLOYMENT.md) — GitOps / Argo CD deployment guide
5. [LOCAL-DEV.md](LOCAL-DEV.md) — local development setup
6. [RUNBOOK.md](RUNBOOK.md) — day-to-day operations
7. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common problems and fixes
8. [THIN_SLICE_SERVICES.md](../apps/THIN_SLICE_SERVICES.md) — local executable truth path for the thin-slice runtime
9. [ZONE_MODEL.md](ZONE_MODEL.md) — policy-bound zone model for edge, workspace, platform, memory, ops, and export lanes
10. [DROPZONE_MEMBRANES.md](DROPZONE_MEMBRANES.md) — ingress membrane outcomes and dropzone semantics
11. [EVENT_BUS_TOPICS.md](EVENT_BUS_TOPICS.md) — initial zone-first topic taxonomy
12. [MEMORY_MESH_INTEGRATION.md](MEMORY_MESH_INTEGRATION.md) — memory runtime integration stance
13. [INTEGRATION-MAP.md](INTEGRATION-MAP.md) — cross-repo integration layer map
14. [OBSERVABILITY.md](OBSERVABILITY.md) — logging, metrics, and tracing
15. [REPRODUCIBILITY.md](REPRODUCIBILITY.md) — reproducible builds and dependency pinning
16. [ROADMAP.md](ROADMAP.md) — planned improvements
17. [STORAGE_INTEGRATION_BLUEPRINT.md](STORAGE_INTEGRATION_BLUEPRINT.md) — multi-store storage architecture

---

## Architectural Decision Records

ADRs live in [`../adr/`](../adr/) (canonical location):

- [ADR-030](../adr/ADR-030-prophet-platform-integration.md) — Prophet Platform as the integration target

---

## Truth hierarchy

- **Standards repos** define norms (storage, TriTRPC, sourceos-spec).
- **prophet-platform** implements and deploys.
- **sociosphere** enforces cross-repo gates.
- **socioprophet-docs** publishes the narrative.
