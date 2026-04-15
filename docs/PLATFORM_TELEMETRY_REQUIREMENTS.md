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

## Cross-repo alignment
- `socioprophet-standards-storage/docs/standards/040-observability-otel.md`
- `socioprophet-standards-storage/docs/standards/041-telemetry-control-plane-and-recovery.md`
- `global-devsecops-intelligence/docs/architecture/telemetry-surface-profile.md`
