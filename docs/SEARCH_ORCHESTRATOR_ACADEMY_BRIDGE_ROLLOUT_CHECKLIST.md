# Search Orchestrator Academy Bridge Rollout Checklist

## Purpose

This checklist operationalizes the Search Orchestrator Academy bridge after its integration into the `fogstack.knowledge` bundle and ArgoCD topology.

The bridge accepts Alexandrian Academy `LearningSearchRecord` artifacts, exposes them through Search Orchestrator query results, gates visibility through local fallback or Policy Fabric decisions, and can persist/search-index records through Lampstand carrier mode.

## Scope

This checklist covers:

- local validation;
- ArgoCD sync order;
- Lampstand carrier storage expectations;
- Policy Fabric endpoint expectations;
- runtime health and debug checks;
- rollback;
- failure modes.

It does not authorize learner action execution, Canon promotion, policy grant creation, or memory writeback.

## Prerequisites

1. `services/search-orchestrator` image is built and pushed to the expected registry tag.
2. `infra/k8s/search-orchestrator/base` renders without local modification.
3. `infra/k8s/search-orchestrator/overlays/carrier` is available for carrier-only deployments.
4. `infra/k8s/search-orchestrator/overlays/policy` is available for carrier plus live Policy Fabric deployments.
5. `infra/argocd/appsets/search-orchestrator-academy-appset.yaml` is committed and visible to ArgoCD.
6. Lampstand storage roots are writable by the Search Orchestrator workload when carrier mode is enabled.
7. Policy Fabric endpoint is reachable only when the policy overlay is selected, and is configured through `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT`.
8. `GET /v1/search/debug/config` must not expose paths, URLs, or secrets.

## Recommended rollout order

1. Run platform validation on the commit to be deployed.
2. Confirm `fogstack.knowledge` includes `services/search-orchestrator` as `academy-search-bridge`.
3. Confirm `search-orchestrator.academy-bridge.v0.1` release manifest references:
   - Search Orchestrator deployment profiles;
   - Search Orchestrator Kustomize overlays;
   - ArgoCD ApplicationSet;
   - `fogstack.knowledge` bundle.
4. Apply or sync `search-orchestrator-academy-carrier` first.
5. Verify `/healthz` returns `status=ok`.
6. Verify `/v1/search/debug/config` reports:
   - `academy_repository.mode == lampstand-carrier`;
   - `academy_policy.mode == local-fallback`.
7. Ingest a controlled `LearningSearchRecord` fixture.
8. Query for a known term through `/v0/search/query` with `cloud_workspace=true`.
9. Confirm carrier payload, event, receipt, catalog, and publication-request artifacts exist under the configured Lampstand state root.
10. Only after carrier mode is healthy, sync `search-orchestrator-academy-policy`.
11. Verify `/v1/search/debug/config` reports:
   - `academy_repository.mode == lampstand-carrier`;
   - `academy_policy.mode == http-policy-fabric`;
   - `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT` configured as a boolean, not as a URL string.
12. Run allowed and denied visibility fixtures to verify Policy Fabric behavior.

## Health gates

Required healthy responses:

- `GET /healthz` returns HTTP 200.
- `GET /v1/search/debug/config` returns HTTP 200.
- Debug config reports modes but not file paths, endpoint URLs, API keys, or secret names.
- `POST /v1/search/ingest/academy` accepts a valid `LearningSearchRecord`.
- `POST /v0/search/query` returns the record only when caller scope permits visibility.
- Lampstand carrier mode emits carrier payloads, events, receipts, catalog entries, and publication requests.

## Rollback plan

Preferred rollback sequence:

1. Revert from `search-orchestrator-academy-policy` to `search-orchestrator-academy-carrier` if the Policy Fabric endpoint is unhealthy.
2. Revert from `lampstand-carrier` to `lampstand-jsonl` or `json-file` only if Lampstand carrier ingestion is failing and search continuity is more important than carrier receipt emission.
3. Revert to `in-memory` only for short-lived lab recovery.
4. Do not delete Lampstand carrier artifacts during rollback unless the artifact root is known corrupt and already backed up.
5. Preserve release evidence records during rollback for forensic traceability.

## Failure modes and remediation

| Failure | Likely cause | Remediation |
| --- | --- | --- |
| Debug config leaks URL/path/secret | Regression in debug config serializer | Block rollout, patch redaction test, do not deploy. |
| `academy_policy.mode` remains `local-fallback` under policy overlay | `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT` missing | Check ConfigMap/Secret overlay and ArgoCD rendered manifest. |
| Policy queries deny all records | Policy Fabric endpoint reachable but returning deny | Inspect Policy Fabric decision record; fall back to carrier-only overlay if necessary. |
| Carrier artifacts not emitted | Lampstand carrier directory or state root misconfigured | Check `SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR` and `SOCIOPROFIT_STATE_HOME`. |
| Query returns record without expected scope | Visibility filter or policy evaluator regression | Block rollout; run visibility tests and inspect emitted policy decision shape. |
| Kustomize overlay renders but pod fails readiness | Image tag or working directory mismatch | Check Search Orchestrator image, Uvicorn command, `/app/services/search-orchestrator` working directory. |

## Completion criteria

The rollout is complete when:

- carrier overlay is healthy;
- policy overlay is healthy or explicitly deferred;
- debug config confirms expected modes;
- ingest and query smoke succeeds;
- Lampstand artifacts are emitted;
- release evidence references the smoke and topology artifacts;
- rollback path has been tested or explicitly documented as deferred.
