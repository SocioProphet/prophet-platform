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
8. [INTEGRATION-MAP.md](INTEGRATION-MAP.md) — cross-repo integration layer map
9. [OBSERVABILITY.md](OBSERVABILITY.md) — logging, metrics, and tracing
10. [REPRODUCIBILITY.md](REPRODUCIBILITY.md) — reproducible builds and dependency pinning
11. [ROADMAP.md](ROADMAP.md) — planned improvements
12. [STORAGE_INTEGRATION_BLUEPRINT.md](STORAGE_INTEGRATION_BLUEPRINT.md) — multi-store storage architecture

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
