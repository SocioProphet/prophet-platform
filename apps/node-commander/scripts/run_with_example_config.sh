#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export NODE_COMMANDER_CONFIG="$APP_DIR/config/example.config.json"
python -m app.cli serve --host 0.0.0.0 --port 8080
