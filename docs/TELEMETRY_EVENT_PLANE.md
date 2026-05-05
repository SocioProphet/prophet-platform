# Telemetry Event Plane

Defines platform runtime telemetry topic families and required event fields.

## Runtime control-plane alignment

This event plane is extended by `docs/TELEMETRY_RUNTIME_CONTROL_PLANE_ALIGNMENT.md`, which binds telemetry to current runtime evidence records including FogStack dry-run records, live-cluster preflight records, identity context, AgentPlane runs, PolicyPlane decisions, parity-readiness records, and evidence indexes.

## Topic families

The platform SHOULD publish or normalize telemetry across these topic families:

- `platform.telemetry.runtime.v1`
- `platform.telemetry.control.v1`
- `platform.telemetry.recovery.v1`
- `platform.telemetry.evidence.v1`
- `platform.telemetry.policy.v1`

## Required correlation

Runtime-control-plane events SHOULD preserve:

- `trace_id`
- `request_id`
- `build_id`
- `artifact_digest`
- `policyplane_decision_id`
- `agentplane_run_id`
- `runtime_dry_run_record_ref`
- `live_cluster_preflight_record_ref`
- `identity_context_ref`
- `parity_readiness_record_ref`
