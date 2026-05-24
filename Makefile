.PHONY: validate validate-repo docs-check drift-check standards-check topology-check lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke test-go test-python-apps test-tools smoke smoke-health smoke-eval-fabric smoke-evidence-receipts smoke-evidence-console validate-phase3 lampstand-smoke validate-phase4 lampstand-vertical-slice-smoke lampstand-zone-smoke zone-router-publication-smoke zone-router-publication-enqueue-smoke semantic-bridge-zone-validation-smoke validate-fogstack validate-storage-suite validate-repo-governance-mvp

validate: validate-repo drift-check standards-check topology-check lattice-surfaces-check lattice-surface-ingestor-smoke lattice-studio-smoke validate-ops-fabric validate-search-academy-deploy validate-search-image-release validate-lampstand-lifecycle validate-zone-stack-audit policy-fabric-endpoint-client-smoke policy-fabric-guarded-workflow-smoke zone-router-publication-local-publish-smoke zone-router-publication-failure-evidence-smoke zone-router-publication-retry-state-smoke zone-router-publication-remote-broker-seam-smoke test-go validate-phase4 test-python-apps test-tools validate-fogstack validate-storage-suite validate-repo-governance-mvp

validate-repo:
	python3 tools/validate_repo.py

validate-repo-governance-mvp:
	python3 tools/validate_repo_governance_mvp.py
	python3 tools/run_repo_governance_mvp.py

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
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli enrich build/lattice-surface-ingestor/lattice-surface-records.json --output build/lattice-surface-ingestor/lattice-surface-enrichments.json
	PYTHONPATH=apps/lattice-surface-ingestor/src python3 -m lattice_surface_ingestor.cli store build/lattice-surface-ingestor/lattice-surface-records.json build/lattice-surface-ingestor/store
	test -s build/lattice-surface-ingestor/lattice-surface-records.json
	test -s build/lattice-surface-ingestor/lattice-surface-enrichments.json
	test -s build/lattice-surface-ingestor/store/manifest.json
