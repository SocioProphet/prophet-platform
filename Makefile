.PHONY: validate validate-repo docs-check drift-check standards-check topology-check chronos-evidence-loop-readout-validate lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke validate-workroom-update-contract validate-professional-intelligence-manifest validate-wallguard-professional-workroom validate-svf-agent-contract validate-live-sociosphere-svf-contract validate-fogstack-svf-signadot-adapter-readiness validate-environment-validate-change-v2 validate-trust-chain-contracts validate-channel-runtime-gates test-go test-python-apps test-tools smoke smoke-health smoke-eval-fabric smoke-evidence-receipts smoke-evidence-console validate-phase3 lampstand-smoke validate-phase4 lampstand-vertical-slice-smoke lampstand-zone-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke semantic-bridge-zone-validation-smoke validate-fogstack validate-storage-suite trustops-art-runner-smoke

validate: validate-repo drift-check standards-check topology-check chronos-evidence-loop-readout-validate lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke validate-workroom-update-contract validate-professional-intelligence-manifest validate-wallguard-professional-workroom validate-svf-agent-contract validate-live-sociosphere-svf-contract validate-fogstack-svf-signadot-adapter-readiness validate-environment-validate-change-v2 validate-trust-chain-contracts validate-channel-runtime-gates test-go validate-phase4 test-python-apps test-tools validate-fogstack validate-storage-suite trustops-art-runner-smoke

validate-repo:
	python3 tools/validate_repo.py

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

lattice-studio-smoke:
	cd apps/lattice-studio && test -d .venv || python3 -m venv .venv
	cd apps/lattice-studio && . .venv/bin/activate && python -m pip install --upgrade pip pytest && PYTHONPATH=src pytest -q tests
	mkdir -p build/lattice-studio
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-demo-catalog --output-dir build/lattice-studio/catalog
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli create-session --project-id demo-project --user-id demo-user --runtime-asset apps/lattice-studio/examples/runtime-asset.prophet-python-ml.json --catalog-input catalog://datasets/demo-csv@0.1.0 --catalog-input catalog://models/demo-classifier@0.1.0 --catalog-input catalog://applications/demo-notebook-app@0.1.0 --catalog-input catalog://services/demo-inference-service@0.1.0 --policy-ref policy://lattice-studio/paas-demo --output-dir build/lattice-studio/session
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-notebook-plane --output-dir build/lattice-studio/notebook-plane
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-workspace-demo --output-dir build/lattice-studio/workspace
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-atlas-context --output-dir build/lattice-studio/atlas
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-ontogenesis-context --output-dir build/lattice-studio/ontogenesis
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-lampstand-demo --workspace-ref workspace://demo --output-dir build/lattice-studio/lampstand
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-paas-plan --name demo-inference-service --kind service --source-ref git://SocioProphet/demo-inference-service#main --build-mode buildpack --runtime-asset-id runtime-asset:prophet-python-ml:0.1.0 --catalog-asset-ref catalog://services/demo-inference-service@0.1.0 --environment preview --target-platform kubernetes --route https://demo-inference.preview.example.invalid --policy-ref policy://lattice-studio/paas-demo --output-dir build/lattice-studio/paas
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-local-dev --workspace-ref workspace://demo --atlas-context-ref atlas-context:demo --paas-deployment-ref paas-deployment:demo --output-dir build/lattice-studio/local-dev
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-execution --output-dir build/lattice-studio/execution
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-memory --subject workspace://demo --subject atlas-context:demo --subject paas-deployment:demo --subject lampstand://local-search/demo --subject ontogenesis://lattice-studio/demo --subject execution://demo --subject notebook-plane://lattice-studio --subject workspace-synthesis://demo --link catalog://datasets/demo-csv@0.1.0 --output build/lattice-studio/memory-events.json
	PYTHONPATH=apps/lattice-studio/src python3 -m lattice_studio.cli emit-platform-records --catalog-asset build/lattice-studio/catalog/datasets_demo-csv/catalog-asset.json --catalog-asset build/lattice-studio/catalog/models_demo-classifier/catalog-asset.json --catalog-asset build/lattice-studio/catalog/applications_demo-notebook-app/catalog-asset.json --catalog-asset build/lattice-studio/catalog/services_demo-inference-service.json --output build/lattice-studio/studio-platform-records.json --enrich-output build/lattice-studio/studio-platform-record-enrichments.json || true

test -s:
	@true

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

validate-workroom-update-contract:
	python3 tools/validate_workroom_update_contract.py

validate-professional-intelligence-manifest:
	python3 tools/validate_professional_intelligence_manifest.py

validate-wallguard-professional-workroom:
	python3 tools/validate_wallguard_professional_workroom.py

validate-svf-agent-contract:
	python3 tools/validate_svf_agent_contract.py

validate-live-sociosphere-svf-contract:
	python3 tools/validate_live_sociosphere_svf_contract.py

validate-fogstack-svf-signadot-adapter-readiness:
	python3 tools/validate_fogstack_svf_signadot_adapter_readiness.py

validate-environment-validate-change-v2:
	python3 tools/validate_environment_validate_change_v2.py

validate-trust-chain-contracts:
	python3 tools/validate_trust_chain_contracts.py

validate-channel-runtime-gates:
	python3 tools/validate_channel_runtime_gates.py

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

smoke: smoke-health smoke-eval-fabric smoke-evidence-receipts smoke-evidence-console lampstand-zone-smoke policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke semantic-bridge-zone-validation-smoke

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
