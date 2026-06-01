# External Fixture Mirrors

Status: governed fixture mirror policy  
Plane: Prophet Platform CI / cross-plane contract validation

## Purpose

This directory contains pinned mirror fixtures copied from adjacent planes for cross-plane DevSecOps Workroom validation.

The mirrors let Prophet Platform validate reference compatibility with AgentPlane and Sociosphere without requiring live connector access, runtime execution, or cross-repo checkout during CI.

## Authority boundary

Mirrored fixtures are not authoritative runtime truth.

Authoritative owners remain:

- AgentPlane for runtime sandbox run records;
- Sociosphere for workspace/environment state and runtime evidence ingestion;
- Prophet Platform for Workroom projection and product/API presentation.

Prophet Platform may validate compatibility against mirrors, but it must not claim ownership of the mirrored records.

## Current mirrors

### AgentPlane

- `agentplane/runtime-sandbox-run.allocated.valid.json`
- `agentplane/runtime-sandbox-run.shared-receipt.valid.json`

Source plane: `SocioProphet/agentplane`

Authoritative source class:

```text
schemas/sandbox/runtime-sandbox-run.v0.1.schema.json
tests/fixtures/sandbox/runtime-sandbox-run.*.json
```

### Sociosphere

- `sociosphere/runtime-evidence-ingestion.allocated.valid.json`
- `sociosphere/runtime-evidence-ingestion.shared-receipt.valid.json`

Source plane: `SocioProphet/sociosphere`

Authoritative source class:

```text
tools/validate_runtime_evidence_ingestion.py
tests/fixtures/environment/runtime-evidence-ingestion.*.json
```

## Mirror sync rule

A mirror may be updated only when at least one of the following is true:

1. the authoritative upstream fixture changed;
2. the cross-plane contract changed;
3. a new cross-plane validation path is added;
4. a stale mirror is explicitly being repaired.

Every mirror update must preserve non-claims stating that the mirror is fixture-scoped and does not execute infrastructure or certify Signadot feature parity.

## Validation

Prophet Platform validates mirror compatibility through:

```text
tools/validate_cross_plane_runtime_handoff.py
```

The validator currently checks:

- compatibility path from AgentPlane allocated fixture to Sociosphere allocated ingestion fixture to Workroom verified receipt fixture;
- shared receipt path where AgentPlane, Sociosphere, and Prophet Workroom all point to one receipt identity.

## Non-claims

External fixture mirrors do not execute sandbox infrastructure.

External fixture mirrors do not certify full runtime feature parity.

External fixture mirrors do not replace AgentPlane or Sociosphere validators.

External fixture mirrors do not authorize production mutation.
