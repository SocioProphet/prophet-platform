.PHONY: engine-guards validate validate-repo validate-regis-acr-integration smoke-regis-acr-service validate-provable-ai-ops-exchange docs-check drift-check standards-check topology-check chronos-evidence-loop-readout-validate lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke grlplus-service-smoke grl-mesh-smoke owl-reasoner-smoke entity-resolution-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke zone-router-publication-dead-letter-smoke validate-workroom-update-contract validate-professional-intelligence-manifest validate-wallguard-professional-workroom validate-wallguard-professional-workroom-runtime validate-svf-agent-contract validate-live-sociosphere-svf-contract validate-fogstack-svf-signadot-adapter-readiness validate-environment-validate-change-v2 validate-trust-chain-contracts validate-channel-runtime-gates test-go test-python-apps test-tools smoke smoke-health smoke-eval-fabric smoke-evidence-receipts smoke-evidence-console validate-phase3 lampstand-smoke validate-phase4 lampstand-vertical-slice-smoke lampstand-zone-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke semantic-bridge-zone-validation-smoke validate-fogstack validate-storage-suite trustops-art-runner-smoke validate-workspace-services test-workspace smoke-workspace workspace-up workspace-down workspace-logs workspace-build prometheus-local-demo validate-workroom-scope-d-adversarial devsecops-workroom-demo validate-proof-artifacts validate-adr-035-contracts validate-helper-causal-receipts validate-svc-substrate-source-control validate-systema-bridge validate-workroom-schemas validate-device-orchestration validate-mutation-evidence validate-fogstack-svf-p2-evidence-gates validate-repo-governance-contracts validate-semantic-governance validate-orggov-runtime-demo
validate: validate-repo validate-regis-acr-integration validate-workspace-prophet-membrane-e2e validate-provable-ai-ops-exchange drift-check standards-check topology-check chronos-evidence-loop-readout-validate lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke grlplus-service-smoke grl-mesh-smoke owl-reasoner-smoke entity-resolution-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke zone-router-publication-dead-letter-smoke validate-workroom-update-contract validate-professional-intelligence-manifest validate-wallguard-professional-workroom validate-wallguard-professional-workroom-runtime validate-svf-agent-contract validate-live-sociosphere-svf-contract validate-fogstack-svf-signadot-adapter-readiness validate-environment-validate-change-v2 validate-trust-chain-contracts validate-channel-runtime-gates test-go validate-phase4 test-python-apps test-tools validate-fogstack validate-storage-suite trustops-art-runner-smoke validate-workroom-scope-d-adversarial devsecops-workroom-demo validate-proof-artifacts validate-adr-035-contracts validate-helper-causal-receipts validate-svc-substrate-source-control validate-systema-bridge validate-workroom-schemas validate-device-orchestration validate-mutation-evidence validate-semantic-governance validate-orggov-runtime-demo


validate-repo:
	python3 tools/validate_repo.py

# Vendored-engine freshness guards. Both consumers vendor their OWN engine tarball, so both
# must be checked: hellgraph-service HAD a guard that nothing invoked (declared in package.json,
# called by no workflow, Makefile or Dockerfile — it never once ran), and lifecycle-warden had
# none at all and drifted five releases behind unnoticed. That is VFP-0001 in the vendor-freshness
# registry. This target is in the validate-target-diagnostics matrix, so it feeds the REQUIRED
# diagnostics-gate: the guards now fail the build instead of decorating a package.json.
engine-guards:
	node apps/hellgraph-service/scripts/check-engine-version.mjs
	node apps/lifecycle-warden/scripts/check-engine-version.mjs
	# Same question, different vendored input: is the ONTOLOGY we ship the one we declare?
	# The 55k KBpedia RC ABox is the vocabulary enrich + semantic typing resolve against, so a
	# drifted copy changes ANSWERS rather than failing (W12). Runtime refuses to load it;
	# this fails the BUILD, so a mismatched artifact never reaches an image.
	node apps/hellgraph-service/scripts/check-ontology-digest.mjs

docs-check:
	python3 tools/validate_repo.py

drift-check:
	python3 tools/check_repo_drift.py

standards-check:
	python3 tools/check_standards_lock.py

topology-check:
	python3 tools/check_transport_topology.py

chronos-evidence-loop-readout-validate:
	python3 tools/validate_chronos_evidence_loop_readout.py

lattice-surfaces-check:
	python3 tools/validate_lattice_surfaces.py

lattice-surface-ingestor-smoke:
	cd apps/lattice-surface-ingestor && test -d .venv || python3 -m venv .venv
	cd apps/lattice-surface-ingestor && . .venv/bin/activate && python -m pip install --upgrade pip pytest && PYTHONPATH=src pytest -q tests
	mkdir -p build/lattice-surface-ingestor
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli ingest contracts/lattice/boot-release-set.v1.example.json contracts/lattice/runtime-asset.v1.example.json --output build/lattice-surface-ingestor/lattice-surface-records.json
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli enrich build/lattice-surface-ingestor/lattice-surface-records.json --output build/lattice-surface-ingestor/lattice-surface-enrichments.json
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli store build/lattice-surface-ingestor/lattice-surface-records.json build/lattice-surface-ingestor/store
	test -s build/lattice-surface-ingestor/lattice-surface-records.json
	test -s build/lattice-surface-ingestor/lattice-surface-enrichments.json
	test -s build/lattice-surface-ingestor/store/manifest.json

entity-resolution-smoke:
	cd apps/entity-resolution && test -d .venv || python3 -m venv .venv
	cd apps/entity-resolution && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests

owl-reasoner-smoke:
	cd apps/owl-reasoner && test -d .venv || python3 -m venv .venv
	cd apps/owl-reasoner && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests

memoryd-smoke:
	cd apps/memoryd && test -d .venv || python3 -m venv .venv
	cd apps/memoryd && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests

node-commander-smoke:
	cd apps/node-commander && test -d .venv || python3 -m venv .venv
	cd apps/node-commander && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && python -m pytest -q

liberty-stack-readout-smoke:
	cd apps/liberty-stack-readout && test -d .venv || python3 -m venv .venv
	cd apps/liberty-stack-readout && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && python -m pytest -q

tritfabric-consumption-api-smoke:
	cd apps/tritfabric-consumption-api && test -d .venv || python3 -m venv .venv
	cd apps/tritfabric-consumption-api && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && pytest -q tests

grl-mesh-smoke:
	cd apps/grl-mesh && test -d .venv || python3 -m venv .venv
	cd apps/grl-mesh && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests

grlplus-service-smoke:
	cd apps/grlplus-service && test -d .venv || python3 -m venv .venv
	cd apps/grlplus-service && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests

lattice-studio-smoke:
	cd apps/lattice-studio && test -d .venv || python3 -m venv .venv
	cd apps/lattice-studio && . .venv/bin/activate && python -m pip install --upgrade pip pytest -r requirements.txt && PYTHONPATH=src pytest -q tests
	mkdir -p build/lattice-studio
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-demo-catalog --output-dir build/lattice-studio/catalog
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli create-session --project-id demo-project --user-id demo-user --runtime-asset apps/lattice-studio/examples/runtime-asset.prophet-python-ml.json --catalog-input catalog://datasets/demo-csv@0.1.0 --catalog-input catalog://models/demo-classifier@0.1.0 --catalog-input catalog://applications/demo-notebook-app@0.1.0 --catalog-input catalog://services/demo-inference-service@0.1.0 --policy-ref policy://lattice-studio/paas-demo --output-dir build/lattice-studio/session
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-notebook-plane --output-dir build/lattice-studio/notebook-plane
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-workspace-demo --output-dir build/lattice-studio/workspace
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli create-session --project-id demo-project --user-id demo-user --runtime-asset apps/lattice-studio/examples/runtime-asset.prophet-python-ml.json --catalog-input catalog://datasets/demo-csv@0.1.0 --catalog-input catalog://models/demo-classifier@0.1.0 --catalog-input catalog://applications/demo-notebook-app@0.1.0 --catalog-input catalog://services/demo-inference-service@0.1.0 --policy-ref policy://lattice-studio/demo --output-dir build/lattice-studio/session
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-atlas-context --output-dir build/lattice-studio/atlas
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-ontogenesis-context --output-dir build/lattice-studio/ontogenesis
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-lampstand-demo --workspace-ref workspace://demo --output-dir build/lattice-studio/lampstand
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-paas-plan --name demo-inference-service --kind service --source-ref git://SocioProphet/demo-inference-service#main --build-mode buildpack --runtime-asset-id runtime-asset:prophet-python-ml:0.1.0 --catalog-asset-ref catalog://services/demo-inference-service@0.1.0 --environment preview --target-platform kubernetes --route https://demo-inference.preview.example.invalid --policy-ref policy://lattice-studio/paas-demo --output-dir build/lattice-studio/paas
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-local-dev --workspace-ref workspace://demo --atlas-context-ref atlas-context:demo --paas-deployment-ref paas-deployment:demo --output-dir build/lattice-studio/local-dev
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-execution --output-dir build/lattice-studio/execution
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-memory --subject workspace://demo --subject atlas-context:demo --subject paas-deployment:demo --subject lampstand://local-search/demo --subject ontogenesis://lattice-studio/demo --subject execution://demo --subject notebook-plane://lattice-studio --subject workspace-synthesis://demo --link catalog://datasets/demo-csv@0.1.0 --output build/lattice-studio/memory-events.json
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-platform-records --catalog-asset build/lattice-studio/catalog/datasets_demo-csv/catalog-asset.json --catalog-asset build/lattice-studio/catalog/models_demo-classifier/catalog-asset.json --catalog-asset build/lattice-studio/catalog/applications_demo-notebook-app/catalog-asset.json --catalog-asset build/lattice-studio/catalog/services_demo-inference-service/catalog-asset.json --output build/lattice-studio/studio-platform-records.json --enrich-output build/lattice-studio/studio-platform-record-enrichments.json
	# Output assertions. These belong to lattice-studio-smoke and must run as part of it:
	# emitting a file is not the same as emitting a NON-EMPTY file, and this leg is wired
	# into the required diagnostics-gate via smoke-target-diagnostics.
	test -s build/lattice-studio/session/notebook-session.json
	test -s build/lattice-studio/session/notebook-session-evidence.json
	test -s build/lattice-studio/catalog/datasets_demo-csv/catalog-asset.json
	test -s build/lattice-studio/catalog/models_demo-classifier/catalog-asset.json
	test -s build/lattice-studio/catalog/applications_demo-notebook-app/catalog-asset.json
	test -s build/lattice-studio/catalog/services_demo-inference-service/catalog-asset.json
	test -s build/lattice-studio/atlas/atlas-context.json
	test -s build/lattice-studio/ontogenesis/ontogenesis-context.json
	test -s build/lattice-studio/lampstand/lampstand-local-search-results.json
	test -s build/lattice-studio/lampstand/datahub-promotion-proposals.json
	test -s build/lattice-studio/paas/paas-deployment-plan.json
	test -s build/lattice-studio/local-dev/local-dev-session.json
	test -s build/lattice-studio/memory-events.json
	test -s build/lattice-studio/studio-platform-records.json

validate-ops-fabric:
	python3 tools/validate_ops_fabric.py

validate-search-academy-deploy:
	python3 tools/validate_search_orchestrator_academy_deploy.py

validate-search-image-release:
	python3 tools/validate_search_orchestrator_image_release.py

validate-lampstand-lifecycle:
	python3 tools/validate_lampstand_lifecycle.py

validate-zone-stack-audit:
	python3 tools/validate_zone_publication_stack_audit.py

policy-fabric-endpoint-client-smoke:
	python3 tools/smoke_policy_fabric_operations_endpoint_client.py

policy-fabric-guarded-workflow-smoke:
	python3 tools/smoke_policy_fabric_guarded_operations_validation.py

zone-router-publication-local-publish-smoke:
	python3 tools/smoke_zone_publication_local_publish.py

zone-router-publication-failure-evidence-smoke:
	python3 tools/smoke_zone_publication_failure_evidence.py

zone-router-publication-retry-state-smoke:
	python3 tools/smoke_zone_publication_retry_state.py

zone-router-publication-remote-broker-seam-smoke:
	python3 tools/smoke_zone_publication_remote_broker_seam.py

zone-router-publication-dead-letter-smoke:
	python3 tools/smoke_zone_router_dead_letter.py

validate-workroom-update-contract:
	python3 tools/validate_workroom_update_contract.py

validate-professional-intelligence-manifest:
	python3 tools/validate_professional_intelligence_manifest.py

validate-wallguard-professional-workroom:
	python3 tools/validate_wallguard_professional_workroom.py

validate-wallguard-professional-workroom-runtime:
	python3 tools/validate_wallguard_professional_workroom_runtime.py

validate-svf-agent-contract:
	python3 tools/validate_svf_agent_contract.py

validate-retention-policy:
	python3 tools/validate_retention_policy.py

validate-live-sociosphere-svf-contract:
	python3 tools/validate_live_sociosphere_svf_contract.py

validate-fogstack-svf-signadot-adapter-readiness:
	python3 tools/validate_fogstack_svf_signadot_adapter_readiness.py

validate-fogstack-svf-p2-evidence-gates:
	python3 tools/validate_fogstack_svf_nonprod_sandbox_observation.py
	python3 tools/validate_fogstack_svf_baseline_fallback_trace.py
	python3 tools/validate_fogstack_svf_network_isolation_observation.py
	python3 tools/validate_fogstack_svf_async_topic_isolation_observation.py
	python3 tools/validate_fogstack_svf_stateful_resource_isolation_observation.py
	python3 tools/validate_fogstack_svf_gitops_reconciliation_observation.py
	python3 tools/validate_fogstack_svf_leak_check_observation.py
	python3 tools/validate_workroom_runtime_parity_bridge.py

validate-environment-validate-change-v2:
	python3 tools/validate_environment_validate_change_v2.py

validate-trust-chain-contracts:
	python3 tools/validate_trust_chain_contracts.py

validate-channel-runtime-gates:
	python3 tools/validate_channel_runtime_gates.py

validate-repo-governance-contracts:
	python3 -m json.tool contracts/repo-governance/schemas/repo-governance-observation.v0.1.json >/dev/null
	python3 -m json.tool contracts/repo-governance/schemas/repo-governance-rule-finding.v0.1.json >/dev/null
	python3 -m json.tool contracts/repo-governance/schemas/repo-governance-ledger-record.v0.1.json >/dev/null
	python3 tools/validate_repo_governance_contracts.py

test-go:
	go test ./libs/go/tritrpcbridge/...
	go test ./apps/api/...
	go test ./apps/gateway/...

test-python-apps:
	cd apps/eval-fabric-api && test -d .venv || python3 -m venv .venv
	cd apps/eval-fabric-api && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt -r requirements-test.txt && pytest -q tests ../knowledge-reason/tests
	cd apps/evidence-receipts && test -d .venv || python3 -m venv .venv
	cd apps/evidence-receipts && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt -r requirements-test.txt && pytest -q tests
	cd apps/evidence-console && test -d .venv || python3 -m venv .venv
	cd apps/evidence-console && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements-test.txt && pytest -q tests
	cd apps/zone-router && test -d .venv || python3 -m venv .venv
	cd apps/zone-router && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements-test.txt && PYTHONPATH=src pytest -q tests
	cd apps/semantic-bridge && test -d .venv || python3 -m venv .venv
	cd apps/semantic-bridge && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements-test.txt && PYTHONPATH=src pytest -q tests

test-tools:
	test -d .venv-tools || python3 -m venv .venv-tools
	. .venv-tools/bin/activate && python -m pip install --upgrade pip && pip install pytest pyyaml jsonschema && pytest -q tools/tests

trustops-art-runner-smoke:
	PYTHONPATH=apps/trustops-art-runner/src python3 tools/smoke_trustops_art_runner.py

smoke: smoke-health smoke-eval-fabric smoke-regis-acr-service smoke-evidence-receipts smoke-evidence-console lampstand-zone-smoke policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke semantic-bridge-zone-validation-smoke

smoke-health:
	bash tools/smoke_tritrpc_health.sh

smoke-eval-fabric:
	bash tools/smoke_eval_fabric.sh

smoke-evidence-receipts:
	bash tools/smoke_evidence_receipts.sh

smoke-evidence-console:
	bash tools/smoke_evidence_console.sh

validate-phase3:
	python3 tools/validate_phase3_contracts.py

lampstand-smoke:
	PYTHONPATH=apps/lampstand/src python3 -m prophet_platform_lampstand.main emit-receipt \
	  --event-type lampstand.smoke \
	  --action Smoke \
	  --status succeeded \
	  --subject-ref service://lampstand \
	  --payload-ref artifact://smoke

validate-phase4:
	python3 tools/validate_phase4_vertical_slice.py

lampstand-vertical-slice-smoke:
	bash apps/lampstand/scripts/vertical_slice_smoke.sh

lampstand-zone-smoke:
	python3 tools/smoke_lampstand_zone.py

zone-router-publication-smoke:
	python3 tools/smoke_zone_publication_plan.py

zone-router-publication-enqueue-smoke:
	python3 tools/smoke_zone_publication_enqueue.py

semantic-bridge-zone-validation-smoke:
	python3 tools/smoke_semantic_bridge_zone_validation.py

validate-fogstack:
	python3 tools/validate_fogstack.py

validate-storage-suite:
	python3 tools/validate_storage_suite.py

.PHONY: validate-office-runtime-contracts
validate-office-runtime-contracts:
	python3 tools/validate_office_runtime_contracts.py

.PHONY: validate-workroom-scope-d-adversarial devsecops-workroom-demo
validate-workroom-scope-d-adversarial:
	python3 tools/validate_devsecops_scope_d_adversarial.py

.PHONY: devsecops-workroom-demo
devsecops-workroom-demo:
	python3 tools/build_devsecops_workroom_demo.py --output-dir build/devsecops-workroom-demo

.PHONY: prometheus-local-demo
prometheus-local-demo:
	python3 tools/run_prometheus_local_demo.py --output-dir build/prometheus/local-demo

.PHONY: fogstack-local-demo
fogstack-local-demo:
	python3 tools/run_fogstack_local_demo.py --pack all --output-dir build/fogstack-local-demo --summary
	python3 tools/check_fogstack_local_demo_artifact_index.py --index build/fogstack-local-demo/demo-artifacts.index.json

.PHONY: fogstack-local-demo-serve
fogstack-local-demo-serve: fogstack-local-demo
	python3 tools/serve_fogstack_local_demo.py --directory build/fogstack-local-demo --host 127.0.0.1 --port 8765

.PHONY: fogstack-local-demo-deploy-plan
fogstack-local-demo-deploy-plan:
	python3 tools/run_fogstack_local_demo_deploy_plan.py --output-dir build/fogstack-local-demo/deploy --summary

.PHONY: fogstack-local-demo-full
fogstack-local-demo-full:
	python3 tools/run_fogstack_local_demo_full.py --output-dir build/fogstack-local-demo --summary

.PHONY: fogstack-parity-readiness
fogstack-parity-readiness:
	python3 tools/run_fogstack_parity_readiness.py --summary

.PHONY: prophet-artifact-smoke
prophet-artifact-smoke:
	python3 tools/smoke_prophet_artifact_runner.py

.PHONY: validate-workspace-prophet-membrane-e2e
validate-workspace-prophet-membrane-e2e:
	python3 tools/validate_workspace_prophet_membrane_e2e.py
	python3 tools/validate_workspace_prophet_claim_projection.py
	python3 tools/validate_workspace_prophet_runtime_receipts.py
	python3 tools/validate_workspace_prophet_value_projection.py

.PHONY: validate-health-ai-demo-readiness
validate-health-ai-demo-readiness:
	python3 tools/validate_health_ai_demo_readiness.py

.PHONY: validate-prophet-mesh-demo-readiness
validate-prophet-mesh-demo-readiness:
	python3 tools/validate_prophet_mesh_demo_readiness.py

# ── OpenTofu IaC ──────────────────────────────────────────────────────────────
TOFU_ENV ?= local
TOFU_DIR = infra/tofu/envs/$(TOFU_ENV)

.PHONY: tofu-fmt tofu-validate tofu-init tofu-plan tofu-output validate-no-provider-leakage

validate-no-provider-leakage:
	python3 tools/validate_no_provider_leakage.py

tofu-fmt:
	tofu fmt -recursive infra/tofu/

tofu-validate:
	@for env in local gcp-landing shared prod; do \
	  echo "--- validating env=$$env ---"; \
	  cd infra/tofu/envs/$$env && tofu init -backend=false -input=false && tofu validate; \
	  cd $(CURDIR); \
	done

tofu-init:
	cd $(TOFU_DIR) && tofu init -upgrade

tofu-plan:
	@if [ "$(TOFU_ENV)" != "local" ]; then \
	  echo "INFO: plan for $(TOFU_ENV) — no apply gate exists yet. Plan only."; \
	fi
	cd $(TOFU_DIR) && tofu plan

tofu-output:
	cd $(TOFU_DIR) && tofu output

# ── Workspace services ────────────────────────────────────────────────────────
WORKSPACE_COMPOSE = infra/local/docker-compose.workspace.yml

.PHONY: validate-workspace-services test-workspace smoke-workspace workspace-build workspace-up workspace-down workspace-logs

validate-workspace-services:
	python3 tools/validate_workspace_services.py

test-workspace:
	test -d .venv-workspace || python3 -m venv .venv-workspace
	. .venv-workspace/bin/activate && python -m pip install --upgrade pip --quiet && pip install pytest pyyaml --quiet
	. .venv-workspace/bin/activate && pytest -q tests/workspace_operations/test_workspace_infra.py

smoke-workspace:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	bash tools/smoke_workspace_services.sh

workspace-build:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running."; exit 1; \
	fi
	docker compose -f $(WORKSPACE_COMPOSE) build

workspace-up:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	docker compose -f $(WORKSPACE_COMPOSE) up -d
	@echo "Stack started. Logs: make workspace-logs"
	@echo "Ports: IMAP=143, SMTP=25, SUBMISSION=587, CalDAV=5232, MinIO=9000, MinIO-console=9001"

workspace-down:
	docker compose -f $(WORKSPACE_COMPOSE) down

workspace-logs:
	docker compose -f $(WORKSPACE_COMPOSE) logs -f

# ── Prophet Mesh + SocioSphere ────────────────────────────────────────────────
MESH_COMPOSE = infra/local/docker-compose.mesh.yml
SOCIOSPHERE_COMPOSE = infra/local/docker-compose.sociosphere.yml
MESH_REPOS_ROOT ?= $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../

.PHONY: validate-mesh-deployment mesh-build mesh-up mesh-down mesh-logs mesh-ps \
        sociosphere-build sociosphere-up sociosphere-down sociosphere-logs \
        full-stack-up full-stack-down full-stack-build

validate-mesh-deployment:
	python3 tools/validate_mesh_deployment.py

mesh-build:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(MESH_COMPOSE) build

mesh-up:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(MESH_COMPOSE) up -d
	@echo "Mesh stack started (6 tiers, 11 services)."
	@echo "Ports: memoryd=8787, policy-fabric=8700, model-router=8710"
	@echo "       agent-registry=8720, agentplane=8730, superconscious=8740"
	@echo "       tritfabric=8750, governance-ledger=8760, prophet-mesh=8780"
	@echo "       qdrant=6333/6334"

mesh-down:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(MESH_COMPOSE) down

mesh-logs:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(MESH_COMPOSE) logs -f

mesh-ps:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(MESH_COMPOSE) ps

sociosphere-build:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(SOCIOSPHERE_COMPOSE) build

sociosphere-up:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(SOCIOSPHERE_COMPOSE) up -d
	@echo "SocioSphere tier started (tiers 7-10, 15 services)."
	@echo "Ports: sociosphere=5000, cloudshell-fog=8080"
	@echo "       hellgraph=8850, regis=8820, sherlock=8810"
	@echo "       catalog=8830, query=8831, devsecops=8840, lattice-forge=8870"
	@echo "       synapseiq=8800-8804, mcp-a2a=8860"

sociosphere-down:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(SOCIOSPHERE_COMPOSE) down

sociosphere-logs:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose -f $(SOCIOSPHERE_COMPOSE) logs -f

# Full stack (mesh + sociosphere together)
full-stack-build: mesh-build sociosphere-build

full-stack-up:
	@if ! docker info >/dev/null 2>&1; then \
	  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."; \
	  exit 1; \
	fi
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose \
	  -f $(MESH_COMPOSE) \
	  -f $(SOCIOSPHERE_COMPOSE) \
	  up -d
	@echo "Full SocioProphet stack started (tiers 0-10, 26 services)."

full-stack-down:
	MESH_REPOS_ROOT=$(MESH_REPOS_ROOT) docker compose \
	  -f $(MESH_COMPOSE) \
	  -f $(SOCIOSPHERE_COMPOSE) \
	  down

# ── Terraform / IaC ───────────────────────────────────────────────────────────
TF_ENV ?= p0-lab
TF_DIR = infra/terraform/environments/$(TF_ENV)

infra-init:
	cd $(TF_DIR) && terraform init -upgrade

infra-plan:
	cd $(TF_DIR) && terraform plan

infra-apply:
	cd $(TF_DIR) && terraform apply

infra-destroy:
	cd $(TF_DIR) && terraform destroy

infra-fmt:
	terraform fmt -recursive infra/terraform/

infra-validate:
	cd infra/terraform/environments/p0-lab && terraform init -backend=false && terraform validate
	cd infra/terraform/environments/p1-single-site && terraform init -backend=false && terraform validate

# ── prophet-cli ───────────────────────────────────────────────────────────────
PROPHET_CLI_DIR ?= $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/../prophet-cli

prophet-cli-install:
	test -d $(PROPHET_CLI_DIR)/.venv || python3 -m venv $(PROPHET_CLI_DIR)/.venv
	$(PROPHET_CLI_DIR)/.venv/bin/pip install -e $(PROPHET_CLI_DIR) -q
	@echo "Installed. Run: source $(PROPHET_CLI_DIR)/.venv/bin/activate && prophet --help"

.PHONY: infra-init infra-plan infra-apply infra-destroy infra-fmt infra-validate prophet-cli-install

validate-regis-acr-integration:
	python3 tools/validate_regis_acr_integration.py

smoke-regis-acr-service:
	python3 tools/smoke_regis_acr_service.py

validate-provable-ai-ops-exchange:
	python3 tools/validate_provable_ai_ops_exchange.py

validate-proof-artifacts:
	python3 tools/validate_proof_artifacts.py

validate-adr-035-contracts:
	python3 tools/validate_adr_035_contracts.py

validate-helper-causal-receipts:
	python3 tools/validate_helper_causal_receipts.py

validate-svc-substrate-source-control:
	python3 tools/validate_svc_substrate_source_control.py

validate-systema-bridge:
	python3 tools/validate_systema_bridge.py

validate-workroom-schemas:
	python3 tools/validate_workroom_schemas.py

validate-device-orchestration:
	python3 tools/validate_device_orchestration.py

validate-mutation-evidence:
	python3 tools/validate_mutation_evidence.py

validate-semantic-governance:
	python3 tools/validate_semantic_governance.py

validate-orggov-runtime-demo:
	python3 tools/validate_orggov_runtime_demo.py

validate-capability-membrane:
	test -d .venv-tools || python3 -m venv .venv-tools
	. .venv-tools/bin/activate && python -m pip install --upgrade pip pytest cryptography >/dev/null && pytest -q tools/tests/test_capability_membrane.py tools/tests/test_membrane_identity.py tools/tests/test_membrane_adversarial.py tools/tests/test_gapi_edge_policy.py tools/tests/test_ghost_audit.py tools/tests/test_proof_of_emptiness.py
	mkdir -p build/capability-membrane
	# CLI exits 3 on a non-allow (here REQUIRE_SIGNATURE→ask); the gate asserts a
	# sealed receipt was still emitted for the deferred decision.
	python3 -m tools.capability_membrane --operation fixtures/capability-membrane/operation-deploy-apply.decision.json --surface deployment --access destructive --tension policy,identity,provenance,evidence,replay,revocation,audit,post_authority_ref --autonomy-level L4 --evidence conductor_response_envelope --out build/capability-membrane/deploy-apply.sealed.json || true
	test -s build/capability-membrane/deploy-apply.sealed.json

.PHONY: validate-isota-tournament
# iSOTA provider-neutral tournament: producer emits spec-valid eval-fabric records
# (provisional — no reproduced facts) and the invariant tests run. Mirrors the CI
# workflow .github/workflows/isota-tournament.yml.
validate-isota-tournament:
	test -d .venv-tools || python3 -m venv .venv-tools
	. .venv-tools/bin/activate && python -m pip install --upgrade pip jsonschema rfc3339-validator pytest >/dev/null && python tools/isota_tournament.py && pytest -q tests/platform_stubs/test_isota_tournament.py

.PHONY: canary-slo-gate-check
# Fail-closed Argo Rollouts SLO gates: an empty Prometheus series must ABORT a
# canary, not promote it ("no data" != "healthy"). tools/check_canary_slo_gate.py
# requires every result-thresholding AnalysisTemplate metric to declare both a
# data-presence successCondition and an absent-data failureCondition. Wired into
# the validate-target-diagnostics matrix so it rides the repo's required gate.
canary-slo-gate-check:
	python3 tools/check_canary_slo_gate.py

.PHONY: rollout-analysis-refs-check
# Self-contained overlays (INV-DEP-9): a Rollout may only reference an AnalysisTemplate the
# overlay renders (namespaced, same ns) or a declared ClusterAnalysisTemplate (clusterScope).
# A dangling ref renders clean under `kubectl kustomize` but the LIVE Rollout controller rejects
# it (InvalidSpec: AnalysisTemplate not found, Degraded/no pods) — the wave-deploy prod incident.
# tools/verify_rollout_analysis_refs.py renders each promote overlay and proves every analysis
# ref resolves. Wired into the validate-target-diagnostics matrix so it rides the required gate.
rollout-analysis-refs-check:
	python3 tools/verify_rollout_analysis_refs.py

.PHONY: overlay-self-contained-check
# Self-contained overlays (INV-DEP-10): a workload (Deployment/Rollout) may only reference a
# ServiceAccount / ConfigMap / PVC the overlay also renders. A dangling ref renders clean under
# `kubectl kustomize` but the LIVE cluster FailedCreate's at pod-create ('serviceaccount not
# found', 0 pods) — the wave-deploy prod incident where the "Self-contained" prod overlay shipped
# a Rollout but not its SA/ConfigMap/PVC. tools/verify_overlay_self_contained.py renders each
# promote overlay and proves every pod-template ref resolves. In the validate-target-diagnostics
# matrix so it rides the required gate; one-click deploy depends on it.
overlay-self-contained-check:
	python3 tools/verify_overlay_self_contained.py

.PHONY: manifest-completeness-check
# DERIVED reference completeness (INV-DEP-11): the reference classes INV-DEP-9 (analysis templates)
# and INV-DEP-10 (SA/ConfigMap/PVC) do NOT cover — Secret refs and image digest-pinning — so a
# novel ref type can't render clean under `kubectl kustomize` and then FailedMount / ImagePullBackOff
# on the live apply before someone hand-writes the next point gate. For every workload in each
# promote overlay: every referenced Secret (secret volumes, envFrom.secretRef, env.secretKeyRef,
# projected secret sources, imagePullSecrets) must be rendered in-set or listed in
# infra/k8s/search-orchestrator/external-secrets.allowlist.yaml, and every image (initContainers +
# containers) must be pinned to a real @sha256 digest (no floating tag, no placeholder digest).
# tools/verify_manifest_completeness.py — sibling of 9/10, in the validate-target-diagnostics matrix.
manifest-completeness-check:
	python3 tools/verify_manifest_completeness.py

.PHONY: fips-conformance-check
# FIPS algorithm conformance in the declared crypto boundary (security/fips-boundary.yaml):
# no non-FIPS algorithm (BLAKE2/3, MD5, SHA-1) may be called inside the boundary, and a
# deployment that declares require_fips_validated_crypto: true must have this gate wired —
# turning a flag nothing read into an enforced control. tools/check_fips_conformance.py.
fips-conformance-check:
	python3 tools/check_fips_conformance.py

.PHONY: imageschemanet-grounding-check
# ImageSchemaNet cartridge (apps/hellgraph-service/ontology/imageschemanet.ttl): the
# embodied-commonsense grounding layer. Verifies the cartridge is structurally sound
# (every image schema has core spatial primitives; every lexical activator activates a
# known schema) and that golden NL->image-schema groundings resolve. Owns its rdflib dep.
imageschemanet-grounding-check:
	python3 -m pip install --quiet 'rdflib==7.6.0' 'pytest>=8,<9'
	python3 tools/imageschema_ground.py
	python3 -m pytest -q tools/tests/test_imageschema_ground.py

.PHONY: no-dangling-path-refs-check
# Blast-radius on refactor (INV-DEP-12): a PR that MOVES/RENAMES/DELETES a repo path must not
# leave any surviving tracked file still referencing the OLD path. That break renders/parses
# clean and only fails when the path is dereferenced — the same "looks fine, fails later" class
# as INV-DEP-9/10, here for repo-path refs. It actually happened: moving
# infra/k8s/search-orchestrator/base/configmap.yaml -> base-support/ silently broke
# tools/validate_search_orchestrator_academy_deploy.py, which hard-coded the old base/ path;
# only CI caught it, after push. tools/verify_no_dangling_path_refs.py diffs HEAD against the
# merge-base with origin/main and fails on a surviving old-path reference (proven both ways by
# tools/tests/test_verify_no_dangling_path_refs.py). NEEDS FULL GIT HISTORY — in CI, check out
# with fetch-depth: 0 (or `git fetch --unshallow`); it is fail-closed if it cannot diff.
no-dangling-path-refs-check:
	python3 tools/verify_no_dangling_path_refs.py

.PHONY: evidence-refs-check
# Evidence-reference verification (INV-DEP-13): every reference a release/evidence artifact makes
# to another repo artifact must RESOLVE — not merely look right. Generalises "a reference must
# resolve" from cluster objects (INV-DEP-9/10) and repo paths (INV-DEP-12) to the EVIDENCE surface
# under releases/: every repo-path ref (paths, lock refs, validation-record refs) must exist and
# parse; every evidence://|file:// URI must resolve (the agent-registry #56 fabricated-URI ghost);
# and every digest-evidence claim (bundle_digest/rulepack_digest) must equal sha256(the file it
# names). Placeholders in *.example.*/*.template.* artifacts are explicit unfilled slots, not
# claims. tools/verify_evidence_refs.py — pure-filesystem, no kubectl; proven both ways by
# tools/tests/test_verify_evidence_refs.py. In the validate-target-diagnostics matrix + preflight.
evidence-refs-check:
	python3 tools/verify_evidence_refs.py

.PHONY: preflight
# Local == CI parity (L5): run the fast, hermetic subset of the REQUIRED validate-target-
# diagnostics matrix locally, in minutes, so path-breaks and gate failures surface BEFORE push
# instead of only in CI after it. Includes the static ref-resolution + blast-radius gates
# (INV-DEP-9/10/12) and the tools test suite; EXCLUDES the slow/infra-heavy legs (kind, go
# build, per-app venvs, docker) and the CI-only real-apply/digest-exists preflight (those still
# run in CI). Prints a PASS / what-to-fix summary and exits non-zero if any leg fails.
# See docs/RESILIENCE_ENGINEERING.md. Opt into the pre-push hook: git config core.hooksPath .githooks
preflight:
	python3 tools/run_preflight.py
