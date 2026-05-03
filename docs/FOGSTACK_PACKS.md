# Fog Stack packs

This document records the current Fog Stack pack taxonomy, product-surface intent, and readiness levels inside `prophet-platform`.

## Decision

Fog Stack should **not** split into separate repositories for AI, Data, Automation, Security, or other future pack categories yet.

The shared trust/release graph is still the dominant implementation concern, and the current pack boundaries do not yet justify independent lifecycles. The right move is to keep engineering in `prophet-platform`, track pack readiness here, and split only when a pack has a clearly independent release cadence, operator lifecycle, support burden, and CI surface.

## Current packs

### Fog Stack Access
- Type: real product surface
- Readiness: 70%
- Repo split now: no
- Why: strongest customer-facing surface so far; remaining work is mainly trust/release hardening, not basic product identity.

### Fog Stack Knowledge
- Type: real product surface
- Readiness: 55%
- Repo split now: no
- Why: clear substrate anchors but more composition-heavy and operationally mixed.

### Fog Stack Evaluation
- Type: real product surface
- Readiness: 55%
- Repo split now: no
- Why: real platform surface, but still more internal than packaged.

### Fog Stack Office / Collaboration
- Type: real product surface (executable-demo posture)
- Readiness: 55%
- Repo split now: no
- Why: an executable collaboration runtime landed via PRs #314–#319 with thread creation, messages, version-aware suggestion status, thread and suggestion resolution, and full event-history behaviors, all covered by behavior tests. JSON schemas exist for thread and suggestion records. Not yet hardened for production auth, durable persistence, or external identity; surface is at executable-demo posture, not production deployment.

### Fog Stack Security / Trust
- Type: strong shared capability
- Readiness: 80% as platform capability / 35% as standalone pack
- Repo split now: no
- Why: the shared trust/release graph is still the dominant engineering concern.

### Fog Stack Registry / Release Distribution
- Type: real product surface (demo/CI posture)
- Readiness: 60%
- Repo split now: no
- Why: the registry/release-distribution lane now includes gated publication, filesystem registry export, registry publication indexes, registry-root metadata, rollback/revocation lifecycle indexes, and local registry metadata signature-verification support across PRs #211–#215, #224, #237, #248, and #324. It is no longer just a future release-plumbing concept. Remaining gaps are network registry publication, production KMS/HSM-backed signing, external identity binding, client-side rollback/revocation enforcement, and operator-facing release-distribution UX. No external registry or production deployment exists on main.

### Fog Stack Data / GovernAI
- Type: fixture-ready product surface
- Readiness: 50%
- Repo split now: no
- Why: upgraded from 30% (packaging view over Knowledge + Evaluation) to 50% following the Lattice Studio/Data/GovernAI vertical slice merged in PRs #299–#308. The full deterministic fixture path now covers product-spine, annotation-to-training, active metadata, trust/reputation signals, and GovernAI routing consumers. Still fixture/demo-only; no live data backend, external data contracts, or production data pipeline exists on main.

### Fog Stack AI / Lattice Studio
- Type: fixture-ready product surface
- Readiness: 45%
- Repo split now: no
- Why: upgraded from 20% (conceptual future pack) to 45% following the Lattice Studio vertical slice in PRs #299–#308. The surface now includes model zoo, prompt/RAG/evaluation lab, publication review/reproduction, runtime profile catalog (three Lattice Forge runtimes), a demo readiness report, and a runtime release readiness fixture. All surfaces are fixture/demo-only; no live inference, model training, serving infrastructure, or production ML pipeline exists on main.

### Fog Stack Automation
- Type: conceptual future pack
- Readiness: 20%
- Repo split now: no
- Why: workflow/orchestration is not yet a distinct first-class product surface.

## Repo split triggers

A future Fog Stack pack should not move into its own repository until most of the following are true:

1. it has an independent release cadence
2. it has a distinct operator lifecycle and deployment surface
3. it has dedicated CI/test obligations that reduce, not increase, repo complexity
4. it has support responsibilities distinct from the shared trust/release substrate
5. the trust/release graph can be shared without duplicating platform-wide signing/evidence logic

## Relationship to `prophet-platform`

`prophet-platform` remains the canonical runtime and deployment substrate.

Fog Stack currently lands here as:
- productization
- conformance
- release metadata
- trust graph
- evidence and sealing machinery

The future packs should therefore be treated as catalog and packaging surfaces until they are mature enough to justify independent repos.
