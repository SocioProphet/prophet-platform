#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-build/prometheus/local-demo}"
ISSUED_AT="${PROMETHEUS_ISSUED_AT:-2026-05-27T21:00:00Z}"

python3 tools/run_prometheus_local_demo.py \
  --output-dir "${OUTPUT_DIR}" \
  --issued-at "${ISSUED_AT}"

python3 tools/validate_prometheus_local_demo.py \
  "${OUTPUT_DIR}/manifest.json"
