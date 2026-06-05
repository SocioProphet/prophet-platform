include Makefile

.PHONY: validate-workspace-prophet-membrane-e2e
validate-workspace-prophet-membrane-e2e:
	python3 tools/validate_workspace_prophet_membrane_e2e.py
	python3 tools/validate_workspace_prophet_claim_projection.py
	python3 tools/validate_workspace_prophet_runtime_receipts.py
