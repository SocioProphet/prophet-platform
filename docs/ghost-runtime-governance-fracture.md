# Ghost runtime governance and fracture integration

## Purpose
This note describes how the Ghost control-plane contracts integrate into the runtime/deployment hub.

## Boundaries
- Standards and schemas live upstream in `socioprophet-standards-storage`.
- Transport fixture contracts live upstream in `TriTRPC`.
- This repository owns runtime harnesses, orchestration wrappers, and CI workflows.

## Runtime lane
The minimum runtime lane should be able to:
1. emit Ghost runtime events
2. validate signed Ghost artifacts
3. run a fracture/failure lane
4. run a governance + registry ceremony lane
5. combine both into one CI-visible result

## Initial implementation shape
This repo adds:
- `tools/registry_governance_ceremony_runner_v0_2.py`
- `tools/combined_governance_fracture_ci_harness_v0_4.py`
- `.github/workflows/ghost-governance-fracture.yml`

## Intended follow-up
Replace these wrappers with the fully wired runtime implementations once the upstream standards and fixtures are landed and vendored or consumed through a stable package path.
