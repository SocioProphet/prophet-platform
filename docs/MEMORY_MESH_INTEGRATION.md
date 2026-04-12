# Memory Mesh Integration

`prophet-platform` should integrate with `memory-mesh` as an upstream runtime dependency rather than reimplementing runtime memory behavior locally.

## Integration rule

- `memory-mesh` remains the canonical upstream for `memoryd` runtime behavior
- `prophet-platform` should host bridge code, deployment wiring, and policy-aware runtime calls
- imported API contracts should be pinned and mirrored only as needed for local validation and runtime safety

## Why this matters

This keeps the platform thin while still making memory a first-class runtime lane in the hosted system.
