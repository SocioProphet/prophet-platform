# Telemetry Runtime Control Plane Alignment

## Purpose
This document aligns the existing platform telemetry baseline with the current `prophet-platform` runtime evidence graph.

The April telemetry baseline remains valid, but the platform has since added identity contracts, FogStack runtime dry-run records, live cluster preflight records, AgentPlane linkage, PolicyPlane linkage, and parity-readiness evidence. Telemetry must now bind to those records explicitly.

## Current runtime anchors
Telemetry consumers SHOULD treat the following platform artifacts as first-class runtime evidence anchors:

- `schemas/runtime/fogstack-runtime-dry-run-record-v0.1.schema.json`
- `schemas/runtime/fogstack-live-cluster-preflight-record-v0.1.schema.json`
- `tools/emit_fogstack_runtime_dry_run_record.py`
- `tools/emit_fogstack_live_cluster_preflight_record.py`
- `tools/check_fogstack_parity_readiness.py`
- `tools/validate_identity_contract_examples.py`
- `docs/PLATFORM_TELEMETRY_REQUIREMENTS.md`
- `docs/TELEMETRY_EVENT_PLANE.md`

## Required telemetry bindings
Runtime telemetry SHOULD emit or preserve correlation for:

- `agentplane_run_id`
- `policyplane_decision_id`
- `artifact_digest`
- `runtime_dry_run_record_ref`
- `live_cluster_preflight_record_ref`
- `identity_context_ref`
- `parity_readiness_record_ref`
- `evidence_index_ref`

## Control-plane signal families
The platform SHOULD distinguish:

- `runtime.bootstrap.*`
- `runtime.identity.*`
- `runtime.dry_run.*`
- `runtime.live_preflight.*`
- `runtime.policy_decision.*`
- `runtime.agentplane_run.*`
- `runtime.recovery.*`
- `runtime.parity_readiness.*`

## Policy alignment
Telemetry MUST preserve whether a runtime path is read-only, dry-run, safely blocked, approval-required, or live-apply capable.

For FogStack live-cluster surfaces, telemetry MUST preserve:

- `live_apply_allowed`
- `mutated_cluster`
- `human_approval_required`
- `preflight_status`

## Relationship to standards
This document consumes the upstream standard:

- `socioprophet-standards-storage/docs/standards/041-runtime-control-plane-telemetry.md`

## Follow-on implementation
The next implementation tranche SHOULD add JSON schemas or examples for canonical runtime telemetry envelopes that reference the existing FogStack runtime and identity records.
