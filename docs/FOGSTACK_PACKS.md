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

### Fog Stack Security / Trust
- Type: strong shared capability
- Readiness: 80% as platform capability / 35% as standalone pack
- Repo split now: no
- Why: the shared trust/release graph is still the dominant engineering concern.

### Fog Stack Data
- Type: emerging packaging view
- Readiness: 30%
- Repo split now: no
- Why: better modeled as a packaging view over Knowledge + Evaluation than as an independent engineering island.

### Fog Stack AI
- Type: conceptual future pack
- Readiness: 20%
- Repo split now: no
- Why: not enough independent runtime/product surface yet.

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
