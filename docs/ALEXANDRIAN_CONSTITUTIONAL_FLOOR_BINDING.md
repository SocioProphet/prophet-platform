# Alexandrian Constitutional Floor Binding (Draft)

## Purpose

This document explains how the Alexandrian constitutional-floor and review-layer objects bind into Prophet Platform runtime enforcement.

The goal is to preserve Alexandrian Academy as the domain source of truth for curriculum, governance, and policy-bearing educational objects, while using Prophet Platform as the runtime execution, conformance, and anomaly-response layer.

## Upstream domain objects

The following objects are expected to originate in `alexandrian-academy`:

- `constitutional-floor-pack`
- `standing-vector-record`
- `power-grant`
- `moderation-event`
- `metamoderation-event`
- `constitutional-review-event`

These objects carry the domain semantics and references to guild charters, constitutional clauses, jurisdiction overlays, and evidence anchors.

## Runtime objects in Prophet Platform

The following runtime contracts are expected in `prophet-platform/contracts/`:

- `AnonymousReputationReceipt.v0.1.json`
- `LinkabilityScope.v0.1.json`
- `MembraneDecision.v0.1.json` (already present)
- future: `RevocationToken.v0.1.json`
- future: `TraceOpenRequest.v0.1.json`

### Binding principles

1. **Floor before action**
   - A runtime service must not authorize a guarded action without a valid constitutional floor ref.

2. **Standing is not power**
   - `standing-vector-record` is evidence for eligibility.
   - `power-grant` is the actual authority object.

3. **Review layers stay distinct**
   - M1 drives first-order moderation.
   - M2 evaluates fairness of M1.
   - M3 evaluates fairness of the system or the case under the constitutional floor.

4. **Anonymous reputation is scoped**
   - `LinkabilityScope` defines how repeated actions remain publicly linkable within scope.
   - `AnonymousReputationReceipt` attaches a pseudonymous commitment, scope, delta, evidence refs, and revocation/trace-open hooks.

5. **Membrane decisions remain explicit**
   - Runtime enforcement decisions should emit `MembraneDecision` receipts when access, disclosure, redaction, quarantine, or escalation decisions are made.

## Suggested runtime flow

1. Alexandrian emits or persists a `moderation-event`.
2. Prophet Platform validates:
   - required constitutional floor ref,
   - required charter refs,
   - power grant existence,
   - time / scope validity.
3. Prophet Platform records a `MembraneDecision` when the runtime action changes visibility, disclosure level, routing, or quarantine posture.
4. If the action contributes to scoped anonymous reputation, Prophet Platform emits an `AnonymousReputationReceipt` using a declared `LinkabilityScope`.
5. If anomaly thresholds or appeal triggers are hit, Prophet Platform routes into M2 or M3 handling and records the resulting events or follow-up decisions.

## Non-derogable checks

The runtime should fail closed when:

- `constitutional_floor_ref` is missing for review-layer actions,
- a `power_grant` is absent or expired,
- an adult-minor private-channel action conflicts with the floor,
- a local overlay attempts to weaken a required invariant,
- a trace-open or revocation action is attempted without the declared authority path.

## Relationship to existing Prophet contracts

`prophet-platform/contracts/README.md` defines the runtime contract family as platform-facing contracts materialized from upstream standards and references. This binding follows that model: Alexandrian keeps the domain schemas; Prophet Platform materializes and enforces runtime receipts, scopes, and decisions.

## Implementation note

This document is intentionally narrow. It does not attempt to define the full cryptographic construction for anonymous reputation. It only defines the minimum honest runtime contract boundary needed to avoid pretending that pseudonymity alone solves scoped accountable participation.
