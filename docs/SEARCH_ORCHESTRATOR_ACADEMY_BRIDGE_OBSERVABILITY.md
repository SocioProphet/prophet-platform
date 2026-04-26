# Search Orchestrator Academy Bridge Observability

## Purpose

This runbook defines the minimum operational observability surface for the Search Orchestrator Academy bridge.

The observability surface is intentionally non-secret. It reports counters and runtime mode metadata, not actor identifiers, queries, endpoint URLs, filesystem paths, or secrets.

## Health endpoints

### `/healthz`

Expected response:

```json
{"status":"ok","service":"search-orchestrator"}
```

Use this endpoint for Kubernetes readiness and liveness probes.

### `/v1/search/debug/config`

Expected fields:

- `academy_repository.mode`
- `academy_repository.configured.*`
- `academy_repository.record_count`
- `academy_policy.mode`
- `academy_policy.configured.policy_fabric_endpoint`
- `academy_policy.configured.timeout_seconds`

This endpoint must not expose:

- file paths;
- endpoint URLs;
- actor IDs;
- query strings;
- API keys;
- secret names.

### `/v1/search/debug/metrics`

Expected counter fields:

- `academy_ingest_total`
- `search_query_total`
- `academy_result_total`
- `policy_decision_allow_total`
- `policy_decision_deny_total`
- `policy_decision_local_total`
- `policy_decision_remote_total`
- `policy_decision_fallback_total`

This endpoint must not expose:

- actor IDs;
- query strings;
- endpoint URLs;
- file paths;
- secrets.

## Operator checks

### Carrier mode check

Expected runtime configuration:

- `academy_repository.mode == lampstand-carrier`
- `academy_policy.mode == local-fallback`

Expected behavior:

- valid Academy ingest increments `academy_ingest_total`;
- query increments `search_query_total`;
- returned Academy records increment `academy_result_total`;
- local policy decisions increment `policy_decision_local_total`.

### Policy mode check

Expected runtime configuration:

- `academy_repository.mode == lampstand-carrier`
- `academy_policy.mode == http-policy-fabric`
- `academy_policy.configured.policy_fabric_endpoint == true`

Expected behavior:

- successful remote decisions increment `policy_decision_remote_total`;
- fallback decisions increment `policy_decision_fallback_total`;
- denied decisions increment `policy_decision_deny_total`.

## Alert candidates

| Signal | Suggested threshold | Meaning |
| --- | --- | --- |
| `/healthz` non-200 | immediate | Service not healthy. |
| `policy_decision_fallback_total` rising | sustained increase | Policy Fabric endpoint degraded or unreachable. |
| `policy_decision_deny_total` sudden spike | sudden increase | Policy change or visibility regression. |
| `academy_ingest_total` flat while upstream active | sustained flatline | Academy publisher or ingress path unhealthy. |
| `academy_result_total` flat while queries active | sustained flatline | Visibility, query, or repository path regression. |
| carrier artifacts missing | immediate | Lampstand carrier path or storage root unhealthy. |

## Dashboard panels

Minimum dashboard panels:

1. Service health.
2. Active repository mode.
3. Active policy mode.
4. Academy ingest counter.
5. Search query counter.
6. Academy result counter.
7. Policy allow/deny counters.
8. Policy local/remote/fallback counters.
9. Carrier artifact emission status.
10. Recent rollout version or Git SHA.

## Incident workflow

1. Check `/healthz`.
2. Check `/v1/search/debug/config`.
3. Check `/v1/search/debug/metrics`.
4. If policy fallback is rising, inspect Policy Fabric availability and endpoint Secret binding.
5. If carrier artifacts are missing, inspect PVC mount, Lampstand state root, and container filesystem permissions.
6. If denied decisions spike, inspect Policy Fabric decision records and Academy record visibility constraints.
7. If debug endpoint exposes sensitive material, block rollout and patch redaction tests.

## Known limitations

The current metrics endpoint is process-local. It is sufficient for preview and controlled rollout validation, but production multi-replica deployments should export the same counters through the selected observability backend or Prometheus-compatible scrape surface.
