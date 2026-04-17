# M2 workstation adapter runtime

## Purpose

This note records how `prophet-platform` should consume the upstream M2 adapter IPC contract family.

The upstream semantic source of truth is `M2_ADAPTER_IPC_PROFILE_0001` in `SocioProphet/socioprophet-agent-standards`.

## Runtime expectations

A runtime consuming M2 should be able to:
- read adapter capability declarations
- validate adapter message shape
- record adapter receipts and failures
- expose adapter results to operator-visible evidence surfaces

## Core operations expected in the first runtime slice

- `info`
- `lock_validate`
- `lock_hash`
- `env_realize`
- `task_run`
- `deps_inventory`

## Downstream implementation rules

1. `prophet-platform` should not redefine the upstream M2 message grammar.
2. Runtime helpers should validate and emit payloads that conform to the upstream schemas.
3. Operator-facing surfaces should preserve error codes and receipt references rather than collapsing them into unstructured log text.
4. Any platform-local helper should remain additive and runtime-facing, not a second standards source of truth.
