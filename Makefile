.PHONY: validate validate-repo docs-check drift-check standards-check topology-check lattice-surfaces-check test-go smoke-health validate-phase3 lampstand-smoke validate-phase4 lampstand-vertical-slice-smoke

validate: validate-repo drift-check standards-check topology-check lattice-surfaces-check test-go

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

test-go:
	go test ./libs/go/tritrpcbridge/...
	go test ./apps/api/...
	go test ./apps/gateway/...

smoke-health:
	bash tools/smoke_tritrpc_health.sh

validate-phase3:
	python3 tools/validate_phase3_contracts.py

lampstand-smoke:
	PYTHONPATH=apps/lampstand/src python3 -m prophet_platform_lampstand.main emit-receipt 	  --event-type lampstand.smoke 	  --action Smoke 	  --status succeeded 	  --subject-ref service://lampstand 	  --payload-ref artifact://smoke

validate-phase4:
	python3 tools/validate_phase4_vertical_slice.py

lampstand-vertical-slice-smoke:
	bash apps/lampstand/scripts/vertical_slice_smoke.sh
