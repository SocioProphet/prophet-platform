#!/usr/bin/env bash
set -euo pipefail

python -m pytest tests/test_http_readout.py tests/test_subject_http_readout.py tests/test_subject_http_missing.py tests/test_subject_cli_helper.py tests/test_combined_readout.py tests/test_combined_readout_receipt_mode.py tests/test_store_subject_discovery.py
