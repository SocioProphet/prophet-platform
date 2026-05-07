#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "${1:-all}" in
  validate)
    python3 tools/validate_regis_acr_integration.py
    ;;
  smoke)
    cd apps/regis-acr-api
    test -d .venv || python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    cd "$ROOT"
    . apps/regis-acr-api/.venv/bin/activate
    python tools/smoke_regis_acr_service.py
    ;;
  all)
    "$0" validate
    "$0" smoke
    ;;
  *)
    echo "usage: $0 [validate|smoke|all]" >&2
    exit 2
    ;;
esac
