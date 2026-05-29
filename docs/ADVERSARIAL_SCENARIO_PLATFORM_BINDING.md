# Adversarial Scenario Platform Binding

Status: draft v0.1

## Purpose

This document defines the Prophet Platform binding for SCOPE-D adversarial scenario references.

The platform binding is intentionally narrow. Prophet Platform may reference upstream governed scenario artifacts, but this tranche does not implement a scenario builder, operator UI, report exporter, runtime executor, live collector, or memory writeback path.

## Ownership

- SCOPE-D owns the executable adversarial scenario JSON contract and Wargames validation.
- Ontogenesis owns the RDF/SHACL semantic projection.
- Memory Mesh owns durable learning/writeback governance.
- Prophet Workspace owns workspace channel/interface substrate contracts.
- Prophet Platform owns this product/runtime reference binding.

## Contract

The platform-facing contract lives at:

- `contracts/security/adversarial-scenario-ref.schema.json`
- `contracts/security/adversarial-scenario-ref.example.json`
- `tools/validate_adversarial_scenario_ref.py`

Validate with:

```bash
make validate-adversarial-scenario-ref
```

## Boundary

The binding is reference-only by default.

It must not grant:

- runtime execution;
- procedure execution authority;
- engagement authorization;
- downstream activation;
- live target access;
- credential access;
- payload delivery;
- state mutation;
- destructive behavior;
- external delivery;
- report export;
- claim promotion;
- memory writeback.

## Required fields

A scenario reference must carry:

- `scenarioRef`;
- SCOPE-D source repo and PR/schema references;
- Ontogenesis semantic reference;
- evidence refs;
- runtime decision receipt refs;
- policy refs;
- explicit semantic non-claims;
- redaction state;
- fail-closed safety and authority fields.

## Non-claims

A platform scenario reference is not a finding, not a report, not a policy update, not a memory update, not an execution request, not a client delivery artifact, and not an authorization envelope.

Platform services may later consume scenario references only after separate API/service design and validation gates are added.
