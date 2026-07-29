# CI path-filter debt

`tools/check_workflow_path_filters.py` re-derives what each path-filtered
workflow actually reads and checks that the filter still covers it. Workflows
in its `VOUCHED` set are enforced and must stay clean; everything below is
**pre-existing** and reported as advisory, so the audit could ship without a
90-workflow rewrite. The list is meant to shrink.

Regenerate with `python3 tools/check_workflow_path_filters.py`.

## Uncovered inputs (10 workflows)

A change to these paths does **not** trigger the validator that reads them —
the check stays green because it is never asked.

- **cloudshell-fog-structural-conformance.yml**
  - tools/validate-cloudshell-fog-structural-conformance.sh reads docs/FOGSTACK_SIGNED_MANIFESTS.md, not matched by paths: filter
  - tools/validate-cloudshell-fog-structural-conformance.sh reads tools/attach_fogstack_manifest_signature.py, not matched by paths: filter
- **deploy-tests.yml**
  - apps/eval-fabric-api/app/tracing.py reads docs/OBSERVABILITY_OTEL_OPENINFERENCE.md, not matched by paths: filter
  - apps/eval-fabric-api/app/tracing_example.py reads infra/local/docker-compose.otel-collector.yml, not matched by paths: filter
  - apps/eval-fabric-api/tests/test_schemas.py reads schemas/eval, not matched by paths: filter
  - runs tests/test_head_to_head.py, which its paths: filter does not match
- **devsecops-investigation-run.yml**
  - tools/validate_devsecops_investigation_run.py reads tests/fixtures/workroom/devsecops-investigation-run.missing-topology-evidence.invalid.json, not matched by paths: filter
  - tools/validate_devsecops_investigation_run.py reads tests/fixtures/workroom/devsecops-investigation-run.projection-evidence-mismatch.invalid.json, not matched by paths: filter
  - tools/validate_devsecops_investigation_run.py reads tests/fixtures/workroom/devsecops-investigation-run.ready-for-rca-without-collected-evidence.invalid.json, not matched by paths: filter
- **devsecops-scope-d-adversarial.yml**
  - tools/validate_devsecops_scope_d_adversarial.py reads tests/fixtures/workroom/devsecops-workroom.post-merge-incident.valid.json, not matched by paths: filter
  - tools/validate_devsecops_scope_d_adversarial.py reads tests/fixtures/workroom/devsecops-workroom.pre-merge-validation-failure.valid.json, not matched by paths: filter
- **mount-intent.yml**
  - libs/python/mount-intent/src/mount_intent/intents.py reads apps/regis-acr-api, not matched by paths: filter
- **personal-intelligence-cell.yml**
  - runs tools/validate_repo.py, which its paths: filter does not match
  - tools/validate_cell_gateway_api.py reads docs/EVENT_BUS_TOPICS.md, not matched by paths: filter
  - tools/validate_cell_lampstand_live_fixture.py reads tools/run_cell_lampstand_live_fixture.py, not matched by paths: filter
  - tools/validate_repo.py reads apps/api/go.mod, not matched by paths: filter
  - tools/validate_repo.py reads apps/gateway/go.mod, not matched by paths: filter
  - tools/validate_repo.py reads contracts/imported/IMPORT_MANIFEST.yaml, not matched by paths: filter
  - tools/validate_repo.py reads contracts/imported/memory-mesh/SOURCE_MANIFEST.yaml, not matched by paths: filter
  - tools/validate_repo.py reads contracts/imported/new-hope/SOURCE_MANIFEST.yaml, not matched by paths: filter
  - tools/validate_repo.py reads contracts/imported/semantic-serdes/SOURCE_MANIFEST.yaml, not matched by paths: filter
  - tools/validate_repo.py reads docs/ARCHITECTURE.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/DROPZONE_MEMBRANES.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/EVENT_BUS_TOPICS.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/MEMORY_MESH_INTEGRATION.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/TRITRPC_PLATFORM_BINDING.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/TRITRPC_SPEC.md, not matched by paths: filter
  - tools/validate_repo.py reads docs/ZONE_MODEL.md, not matched by paths: filter
  - tools/validate_repo.py reads infra/k8s/argo-cd/appsets/socioprophet-appset.yaml, not matched by paths: filter
  - tools/validate_repo.py reads tools/run_prophet_understand_vertical_slice.py, not matched by paths: filter
  - tools/validate_repo.py reads tools/validate_professional_intelligence.py, not matched by paths: filter
  - tools/validate_repo.py reads tools/validate_prophet_understand.py, not matched by paths: filter
- **preflight-deploy-contract.yml**
  - tools/preflight_deploy_contract.py reads apps/embeddings, not matched by paths: filter
- **professional-intelligence-gate4.yml**
  - tools/validate_professional_intelligence.py reads contracts/evidence/adoption-event.schema.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/evidence/adoption-event.v0.1.example.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/institution/institution-entity.schema.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/institution/institution-entity.v0.1.example.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/policy/obligation.schema.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/policy/obligation.v0.1.example.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/risk/conflict-check.schema.json, not matched by paths: filter
  - tools/validate_professional_intelligence.py reads contracts/risk/conflict-check.v0.1.example.json, not matched by paths: filter
- **sourceos-contracts.yml**
  - tools/smoke_sourceos_synthetic_boot_fingerprint.py reads tools/check_sourceos_boot_fingerprint_compliance.py, not matched by paths: filter
- **tofu-plan.yml**
  - runs tools/validate_no_provider_leakage.py, which its paths: filter does not match
  - tools/validate_no_provider_leakage.py reads infra/argocd, not matched by paths: filter
  - tools/validate_no_provider_leakage.py reads infra/k8s, not matched by paths: filter
  - tools/validate_no_provider_leakage.py reads infra/local, not matched by paths: filter

## No unfiltered push-on-main trigger (82 workflows)

Filtered on `pull_request` with no unfiltered push-on-main run, so a wrong
filter means the check never runs at all rather than running at merge time.
Adding the safety net is cheap and should come first.

- agent-action-trace-contracts.yml
- cloudshell-fog-structural-conformance.yml
- cross-repo-orchestration-interop.yml
- deploy-tests.yml
- devsecops-action-grant.yml
- devsecops-agentplane-handoff.yml
- devsecops-gaia-topology.yml
- devsecops-investigation-run.yml
- devsecops-postmortem-lesson.yml
- devsecops-regression-promotion.yml
- devsecops-scope-d-adversarial.yml
- devsecops-workroom-demo-readiness.yml
- devsecops-workroom-rca-guards.yml
- devsecops-workroom-report.yml
- fogstack-agent-core-plan.yml
- fogstack-agent-machine-node-profile.yml
- fogstack-apply-plan-index.yml
- fogstack-apply-plan-parity.yml
- fogstack-approval-intent.yml
- fogstack-deploy-plan.yml
- fogstack-filesystem-registry-root.yml
- fogstack-filesystem-registry.yml
- fogstack-gitops-bundle.yml
- fogstack-kubernetes-manifests.yml
- fogstack-live-apply-plan.yml
- fogstack-local-cluster-runtime.yml
- fogstack-local-demo.yml
- fogstack-manifest-promotion.yml
- fogstack-manifest-publication.yml
- fogstack-registry-lifecycle.yml
- fogstack-registry-metadata-signatures.yml
- fogstack-registry-publication.yml
- fogstack-registry-root.yml
- fogstack-release-proof-canonical-refs.yml
- fogstack-release-proof.yml
- fogstack-runtime-contract.yml
- fogstack-validation.yml
- fogstack-wider-release-graph.yml
- ghost-event-v3-validate.yml
- ghost-governance-fracture.yml
- ghost-v3-combined-control-plane.yml
- mount-intent.yml
- multidomain-geospatial-program-state.yml
- openai-research-mcp-smoke.yml
- ops-fabric-api.yml
- osm-map-api.yml
- personal-intelligence-cell.yml
- preflight-deploy-contract.yml
- probe-contract.yml
- professional-intelligence-gate4.yml
- prometheus-agentplane-policy-provenance.yml
- prometheus-agentplane-schema-pin.yml
- prometheus-jsonld.yml
- prometheus-local-demo.yml
- prometheus-neurosymbolic-contracts.yml
- prometheus-ontogenesis-compat.yml
- prometheus-optional-pysr.yml
- prometheus-pysr-mvp.yml
- prometheus-sindy-fast-path.yml
- prometheus-sindy-run-artifact-emission.yml
- prometheus-sr-run-artifact-emission.yml
- provider-binding-evidence.yml
- provider-binding-validation.yml
- reasoning-failure-runner.yml
- regis-acr-service.yml
- search-orchestrator-image.yml
- search-orchestrator-multicloud-rollout.yml
- search-orchestrator.yml
- socioprophet-api-image.yml
- sourceos-contracts.yml
- telemetry-runtime-slice.yml
- tofu-plan.yml
- tritfabric-consumption-api-stubs.yml
- tritrpc-gateway-image.yml
- validate-change-v2-agentplane-run-link.yml
- validate-forensic-genesis-edge-tightening.yml
- validate-forensic-genesis-edge.yml
- validate-telemetry.yml
- wopi-host-validation.yml
- workspace-context.yml
- workspace-services-image.yml
- workspace-terraform-validate.yml

