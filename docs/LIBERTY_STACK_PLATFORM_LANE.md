# Liberty Stack platform lane

## Purpose

This document defines the first runtime-facing platform lane for Liberty Stack inside `prophet-platform`.

The upstream normative profiles and schemas live in `SocioProphet/socioprophet-agent-standards` under the AgentOS, M2 adapter IPC, and Liberty Stack contract family.

This repository is the downstream runtime and operator home for:
- provider adapter execution
- verification and replay execution
- cutover workflow handling
- operator-facing evidence surfaces

## Scope of this lane

This platform lane is responsible for consuming the upstream standards and turning them into:
- repo-native validators
- runtime helpers and emitters
- event contracts for workflow execution
- operator runbooks and evidence surfaces

## Upstream dependencies

This lane assumes upstream standards for:
- `AGENTOS_SPEC_0001`
- `M2_ADAPTER_IPC_PROFILE_0001`
- `LIBERTY_STACK_PROFILE_0001`

## First runtime concerns

The first runtime slice should cover:
1. manifest validation
2. provider adapter invocation and receipts
3. replay and verification execution
4. cutover approval recording

## Deliberate limits

This first lane note does not yet define:
- full UI implementation
- Linux packaging or bootstrap behavior
- provider-specific adapters

Those remain downstream follow-on work after this lane shape is accepted.
