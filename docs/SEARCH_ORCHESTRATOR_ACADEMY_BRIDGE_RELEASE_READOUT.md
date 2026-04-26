# Search Orchestrator Academy Bridge Release Readout

## Executive summary

The Search Orchestrator Academy bridge is now integrated across the Academy explanation chain, platform search ingestion, Lampstand carrier evidence, Policy Fabric visibility decisions, Kubernetes deployment overlays, ArgoCD topology, and FogStack release evidence.

The bridge connects Alexandrian Academy learning-loop explanation artifacts to the platform search plane without granting authority, executing learner actions, bypassing Canon governance, or writing memory implicitly.

## Release lane

- Component: `services/search-orchestrator`
- Release lane: `academy-bridge`
- Bundle: `bundles/fogstack.knowledge-v0.1.yaml`
- ArgoCD topology: `infra/argocd/appsets/search-orchestrator-academy-appset.yaml`
- Release manifest: `releases/manifests/search-orchestrator.academy-bridge.manifest.json`
- Validation evidence: `releases/evidence/search-orchestrator.academy-bridge.validation.record.json`

## End-to-end path

1. Alexandrian Academy emits a `LearningLoopRecord`.
2. Academy tooling derives a `LearningActionExplanation`.
3. Academy tooling derives a `LearningSearchRecord` for retrieval.
4. Academy tooling derives a `LearningMemoryRecord` for memoryd-compatible writeback when explicitly used.
5. Search Orchestrator ingests `LearningSearchRecord` through `POST /v1/search/ingest/academy`.
6. Search Orchestrator query path exposes Academy results through `/v0/search/query` when caller scope and policy permit.
7. Visibility is evaluated by local fallback or by a live Policy Fabric endpoint when explicitly configured.
8. Lampstand carrier mode materializes Academy search records as carrier payloads and emits carrier, event, receipt, catalog, and publication-request artifacts.
9. ArgoCD ApplicationSet deploys carrier and Policy Fabric variants.
10. FogStack release evidence records the deployment profile, smoke tests, and topology artifacts.

## Landed repository surfaces

### Alexandrian Academy

- Learning-loop stack binding.
- `LearningLoopRecord` contract and validation.
- `LearningActionExplanation` generator and validation.
- `LearningSearchRecord` export.
- `LearningMemoryRecord` export.
- Guarded memoryd write helper.
- Guarded search publisher.
- Bundle publisher.
- Fake-endpoint E2E smoke.

### Policy Fabric

- Academy search visibility request schema.
- Academy search visibility decision schema.
- Request/decision examples.
- Contract validation wired into repo health.

### Prophet Platform

- Search Orchestrator Academy ingest endpoint.
- Academy search repository seam.
- In-memory, JSON-file, JSONL, and Lampstand carrier repository modes.
- Policy Fabric-shaped local fallback decisions.
- Live Policy Fabric HTTP evaluator adapter.
- Safe runtime config endpoint.
- Local compose profile.
- Kubernetes base and overlays.
- ArgoCD ApplicationSet.
- FogStack knowledge bundle membership.
- Release manifest and validation evidence.

## Runtime modes

| Mode | Use case | Persistence | Policy |
| --- | --- | --- | --- |
| `in-memory` | lab only | process-local | local fallback |
| `json-file` | simple durable local test | JSON file | local fallback |
| `lampstand-jsonl` | lightweight indexing export | JSONL | local fallback |
| `lampstand-carrier` | receipt-bearing local/search substrate | Lampstand carrier artifacts | local fallback |
| `lampstand-carrier-policy` | production-like governed visibility | Lampstand carrier artifacts | live Policy Fabric endpoint |

## Safety boundaries

The release preserves these boundaries:

- no learner action execution;
- no Canon promotion;
- no policy grant creation;
- no implicit memory writeback;
- no secret or endpoint URL exposure through debug config;
- Policy Fabric endpoint calls are explicit and timeout-bounded;
- local fallback remains available for continuity when no Policy Fabric endpoint is configured.

## Evidence and tests

Primary evidence paths:

- `services/search-orchestrator/tests/test_academy_lampstand_deployment_smoke.py`
- `services/search-orchestrator/tests/test_academy_lampstand_carrier_real_smoke.py`
- `services/search-orchestrator/tests/test_debug_config.py`
- `tools/validate_search_orchestrator_academy_deploy.py`
- `releases/evidence/search-orchestrator.academy-bridge.validation.record.json`

Primary validation gates:

- Search Orchestrator service workflow.
- Platform `validate` workflow.
- FogStack Validation.
- FogStack Release Proof.
- FogStack Wider Release Graph.
- FogStack Manifest Publication and Promotion.
- Premerge audit.

## Known gaps

1. The Policy Fabric endpoint is supported, but this release does not deploy the Policy Fabric service itself.
2. The Search Orchestrator image reference remains a deployment placeholder until image build/publish automation pins a release tag or digest.
3. ArgoCD topology exists, but cluster-specific sync waves, RBAC, and Secret/ExternalSecret profiles are not yet modeled.
4. Lampstand carrier storage currently uses local filesystem roots; production PVC/storage-class policy still needs explicit profile binding.
5. Runtime dashboards and alerting for Academy bridge health are not yet defined.

## Release posture

This tranche is suitable for preview release as part of `fogstack.knowledge` under controlled operator rollout. It is not yet a full production GA posture because image digests, storage class policy, cluster RBAC, Secret profiles, and live Policy Fabric deployment binding remain to be finalized.
