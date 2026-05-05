# Platform Telemetry Requirements

This document defines runtime telemetry requirements for `prophet-platform`.

## Required behavior
- buffered bootstrap logging before the final sink is ready
- OpenTelemetry traces, logs, and metrics across services
- error tiering: recoverable, caught, uncaught
- stable query identity via `query_key` and `query_hash`
- cache instrumentation for hit, miss, write failure, and recovery
- no unbounded localStorage persistence for large or paginated payloads
- no write-on-read persistent cache mutation
- scoped recovery instead of broad destructive cache purges
- batched sender support with compression, retry, and unload delivery where supported
- transport coverage across `fetch`, `XMLHttpRequest`, and beacon-style unload delivery
- typed runtime-policy telemetry for retry, stream, cache, polling, connector-routing, and redaction behavior

## Required fields
Signals should include:
- `event_name`
- `signal_class`
- `source`
- `ts_ms`
- `build_id`
- `environment`
- `trace_id` or `request_id`

Where relevant also include:
- `span_id`
- `query_hash`
- `cache_key`
- `error_tier`
- `error_boundary`
- `recovery_policy`
- `artifact_digest`
- `policy_decision_id`
- `agentplane_run_id`
- `runtime_dry_run_record_ref`
- `live_cluster_preflight_record_ref`
- `identity_context_ref`

## Runtime control-plane alignment
Runtime telemetry must align with `docs/TELEMETRY_RUNTIME_CONTROL_PLANE_ALIGNMENT.md` for current FogStack dry-run, live-preflight, identity, PolicyPlane, AgentPlane, and parity-readiness evidence surfaces.

## Cross-repo alignment
- `socioprophet-standards-storage/docs/standards/040-observability-otel.md`
- `socioprophet-standards-storage/docs/standards/041-runtime-control-plane-telemetry.md`
- `global-devsecops-intelligence/docs/architecture/telemetry-surface-profile.md`
- `global-devsecops-intelligence/docs/architecture/runtime-control-plane-telemetry-alignment.md`
