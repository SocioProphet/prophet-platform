#!/usr/bin/env bash
set -euo pipefail
python3 tools/render_platform_contracts.py
pytest -q tests/platform_stubs/test_wave1_stubs.py tests/platform_stubs/test_dashboard_bff_overview_contract.py
