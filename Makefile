.PHONY: validate validate-repo docs-check drift-check standards-check topology-check lattice-surfaces-check lattice-surface-ingestor-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke test-go test-python-apps test-tools smoke smoke-health smoke-eval-fabric smoke-evidence-receipts smoke-evidence-console validate-phase3 lampstand-smoke validate-phase4 lampstand-vertical-slice-smoke lampstand-zone-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke semantic-bridge-zone-validation-smoke validate-fogstack validate-storage-suite

validate: validate-repo drift-check standards-check topology-check lattice-surfaces-check lattice-surface-ingestor-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke test-go validate-phase4 test-python-apps test-tools validate-fogstack validate-storage-suite

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

lattice-surfaces-check:
	python3 tools/validate_lattice_surfaces.py

lattice-surface-ingestor-smoke:
	cd apps/lattice-surface-ingestor && test -d .venv || python3 -m venv .venv
	cd apps/lattice-surface-ingestor && . .venv/bin/activate && python -m pip install --upgrade pip pytest && PYTHONPATH=src pytest -q tests
	mkdir -p build/lattice-surface-ingestor
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli ingest contracts/lattice/boot-release-set.v1.example.json contracts/lattice/runtime-asset.v1.example.json --output build/lattice-surface-ingestor/lattice-surface-records.json
	test -s build/lattice-surface-ingestor/lattice-surface-records.json

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
	cd apps/evidence-console && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt -r requirements-test.txt && pytest -q tests
	cd apps/zone-router && test -d .venv || python3 -m venv .venv
	cd apps/zone-router && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements-test.txt && PYTHONPATH=src pytest -q tests
	cd apps/semantic-bridge && test -d .venv || python3 -m venv .venv
	cd apps/semantic-bridge && . .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements-test.txt && PYTHONPATH=src pytest -q tests

test-tools:
	test -d .venv-tools || python3 -m venv .venv-tools
	. .venv-tools/bin/activate && python -m pip install --upgrade pip && pip install pytest pyyaml jsonschema && pytest -q tools/tests

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
