# GhostEventV3 runtime note

## Purpose
This note records the runtime implications of the Event-IR → GhostEvent interop specification.

## Scope
GhostEventV3 extends the runtime event envelope with semantic basis-binding fields:
- `prime_registry_ref`
- `prime_registry_state_hash`
- `event_ir_hash`
- `prime_vector`

## Runtime expectations
Runtime emitters SHOULD:
- derive GhostEventV3 from canonical Event-IR
- include registry-binding fields when prime-topic semantics are present
- compute canonical hashes before signing
- preserve the malformed vs blocked distinction during validation

## Minimal runtime lane
A minimal runtime lane SHOULD be able to emit:
- `layer_touch`
- `contradiction_fracture`
- signed GhostEventV3 wrappers for those events

## Notes
This is a narrow second-wave runtime landing that complements the first Ghost runtime governance and fracture scaffold without forcing a large refactor.
