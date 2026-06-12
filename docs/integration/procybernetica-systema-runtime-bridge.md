# ProCybernetica Systema — Prophet Platform Runtime Bridge

Status: integration contract draft v0.1.

## Authority boundary

**Prophet Platform consumes Systema standards and evidence refs. It does not own the doctrine.**

- Systema profiles, conformance requirements, and inventory control doctrine live in `SocioProphet/ProCybernetica`.
- Concrete ontology and world-model surfaces are owned by `SocioProphet/Ontogenesis`.
- Search catalog surfaces are owned by `SocioProphet/sherlock-search`.
- World-scenario surfaces are owned by `SocioProphet/GAIA`.
- Execution evidence is owned by `SocioProphet/agentplane`.
- SourceOS events are owned by `SourceOS-Linux/sourceos-spec`.
- Delivery Excellence metrics are owned by their canonical repos.

Prophet Platform exposes runtime surfaces that **bridge** these upstream refs into deployable evidence envelopes, policy gates, and audit receipts.

## What prophet-platform owns at this bridge

- `contracts/systema-evidence-ref.example.json` — canonical example of a Systema evidence reference consumed by the platform
- `tools/validate_systema_bridge.py` — validates required fields on evidence refs without replacing upstream schemas
- Runtime surfaces that should expose Systema conformance status (listed below)

## Runtime surfaces that should expose Systema conformance status

| Surface | Systema concern |
|---|---|
| AgentPlane cycle receipts | Conformance with `SYSTEMA_V0_CONFORMANCE.md` claim modes |
| Policy Fabric gates | Evaluate `membrane_boundary_profile` boundary claims |
| Evidence console | Render `source_confidence_profile` and `projection_loss_profile` quality fields |
| Fog Stack service manifests | Declare `dymaxion_service_metric_profile` metric refs |
| Ontogenesis concept entries | Bind to Systema concept conformance checks |

## Evidence ref types

A Systema evidence ref is a structured pointer to an upstream canonical authority. Required fields:

- `ref_type` — category of reference (see enum in `systema-evidence-ref.example.json`)
- `canonical_source` — repo/path or URI of the upstream authority
- `ref_id` — opaque stable identifier within that authority
- `observed_at` — when this ref was resolved
- `conformance_claim` — what the platform asserts about this ref
- `evidence_quality` — `complete`, `partial`, `degraded`, `insufficient`

## Required reading (upstream)

- `SocioProphet/ProCybernetica/docs/integration/SYSTEMA_PATTERN_INVENTORY_CONTROL.md`
- `SocioProphet/ProCybernetica/docs/integration/SYSTEMA_ESTATE_ABSORPTION_PLAN.md`
- `SocioProphet/ProCybernetica/docs/conformance/SYSTEMA_V0_CONFORMANCE.md`
- `SocioProphet/ProCybernetica/profiles/source_confidence_profile.yaml`
- `SocioProphet/ProCybernetica/profiles/projection_loss_profile.yaml`
- `SocioProphet/ProCybernetica/profiles/membrane_boundary_profile.yaml`
- `SocioProphet/ProCybernetica/profiles/dymaxion_service_metric_profile.yaml`

## Validation

```
make validate-systema-bridge
```

Or directly:

```
python3 tools/validate_systema_bridge.py contracts/systema-evidence-ref.example.json
```
