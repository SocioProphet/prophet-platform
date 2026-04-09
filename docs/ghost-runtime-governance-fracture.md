# Ghost runtime governance and fracture integration

## Purpose
This note describes how the Ghost control-plane contracts integrate into the runtime and deployment hub.

## Ownership boundaries
- `socioprophet-standards-storage` owns schemas and standards text.
- `TriTRPC` owns fixture contracts and transport semantics.
- `prophet-platform` owns runtime wrappers, workflows, and deployment-facing integration.

## Minimum runtime lane
The runtime lane should be able to:
1. run a registry-governance ceremony,
2. run a runtime fracture lane,
3. combine both into one CI-visible result,
4. publish machine-readable reports as workflow artifacts.

## Initial landing
This repository adds small wrappers and a workflow so the lane is visible now and can be replaced by the concrete runtime implementations as the upstream standards and fixtures are imported.
