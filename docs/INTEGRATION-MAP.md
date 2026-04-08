# Integration Map — Prophet Platform

## Overview

Prophet Platform is the **operational integration point** for the SocioProphet ecosystem.
It consumes contracts from upstream standards repos and exposes runtime services.

---

## Layer model

```
┌─────────────────────────────────────────────────────────┐
│  socioprophet-docs  (narrative / external-facing docs)   │
├─────────────────────────────────────────────────────────┤
│  sociosphere        (cross-repo governance gates)        │
├─────────────────────────────────────────────────────────┤
│  prophet-platform   (THIS REPO — runtime + infra)        │
│    apps/api · apps/gateway · apps/socioprophet-web        │
│    infra/k8s (GitOps)                                    │
├─────────────────────────────────────────────────────────┤
│  Standards repos (consumed as pinned references)         │
│    socioprophet-standards-storage                         │
│    sourceos-spec                                          │
│    TriTRPC                                                │
└─────────────────────────────────────────────────────────┘
```

---

## Inputs (what this repo consumes)

| Source repo | What we consume | How |
|-------------|----------------|-----|
| `TriTRPC` | RPC framing spec + library | Pinned dependency / spec excerpt in `docs/TRITRPC_SPEC.md` |
| `socioprophet-standards-storage` | Canonical object schemas (Observation, Claim, etc.) | Referenced in `schemas/` and `contracts/` |
| `sourceos-spec` | OpenAPI/AsyncAPI surface contracts | Referenced by gateway routing |

---

## Outputs (what this repo exposes)

| Component | Interface | Consumers |
|-----------|-----------|-----------|
| `apps/api` | UDS TritRPC — `Health.Ping` | gateway, internal services |
| `apps/gateway` | HTTP/WS on `:8080` | socioprophet-web, external clients |
| `apps/socioprophet-web` | Browser UI | human operators |
| `infra/k8s/` | Kustomize manifests | Argo CD + cluster operators |

---

## Event contracts

See `contracts/` for versioned JSON event schemas:
- `EmbeddingComputed.v0.1.json`
- `LensOutput.v0.1.json`
- `TopicAssigned.v0.1.json`

---

## Cross-repo ADR reference

- [ADR-030](../adr/ADR-030-prophet-platform-integration.md) — Prophet Platform as the integration target
