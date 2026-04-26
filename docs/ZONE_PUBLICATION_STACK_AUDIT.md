# Zone publication stack audit

## Purpose

This audit records the stale zone-publication PR stack and defines the next clean review surface.

Stale stack:

- #142 — zone publication validation and local transport runtime
- #156 — zone-router transport adapters and lifecycle outcomes
- #173 — retry-aware zone publication lifecycle

## Decision

Do not merge the stale stack as-is.

The stack was built across old branch bases and spans semantic validation, transport adapters, publication outcomes, retry state, contracts, smoke paths, and Makefile wiring. It should be replaced by a current-main review unit with explicit boundaries and fresh CI proof.

## Replacement scope

A replacement review unit should account for:

1. semantic-bridge validation for zone publication artifacts
2. zone-router semantic gate integration
3. local publication outcome emission
4. adapterized transport modes
5. delivery artifact contract
6. retry and attempt state
7. publication outcome linkage
8. smoke coverage for semantic validation and transport publish
9. Makefile wiring for tests and smokes
10. Sociosphere build-intelligence registration after merge

## Files implicated by stale stack

PR #142:

- `Makefile`
- `apps/semantic-bridge/requirements-test.txt`
- `apps/semantic-bridge/src/semantic_bridge/main.py`
- `apps/semantic-bridge/src/semantic_bridge/validators.py`
- `apps/semantic-bridge/tests/test_validators.py`
- `apps/zone-router/src/zone_router/main.py`
- `apps/zone-router/src/zone_router/semantic_gate.py`
- `apps/zone-router/src/zone_router/transport.py`
- `apps/zone-router/tests/test_publish.py`
- `apps/zone-router/tests/test_semantic_integration.py`
- `apps/zone-router/tests/test_transport.py`
- `contracts/ZonePublicationOutcome.v0.1.json`
- `tools/smoke_semantic_bridge_zone_validation.py`
- `tools/smoke_zone_router_transport_publish.py`

PR #156:

- `apps/zone-router/src/zone_router/main.py`
- `apps/zone-router/src/zone_router/transport.py`
- `apps/zone-router/src/zone_router/transport_adapters.py`
- `apps/zone-router/tests/test_publish_runtime.py`
- `apps/zone-router/tests/test_transport_adapters.py`
- `contracts/ZonePublicationDelivery.v0.1.json`
- `contracts/ZonePublicationOutcome.v0.1.json`
- `tools/smoke_zone_router_transport_publish.py`

PR #173:

- `apps/zone-router/src/zone_router/retry_state.py`
- `apps/zone-router/src/zone_router/transport.py`
- `apps/zone-router/tests/test_retry_lifecycle.py`
- `contracts/ZonePublicationFailureEvidence.v0.1.json`
- `contracts/ZonePublicationOutcome.v0.1.json`
- `tools/smoke_zone_router_transport_publish.py`

## Software review

Correctness: the stale stack is directionally useful but not merge-safe.

Risk: direct merge would mix old-base runtime changes, contracts, tests, and Makefile edits into current main without a clean review surface.

Next action: land this audit, close #142/#156/#173 as superseded, then open a current-main implementation PR for the minimal safe replacement slice.
