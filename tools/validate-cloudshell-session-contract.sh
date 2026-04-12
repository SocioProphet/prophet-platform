#!/usr/bin/env bash
set -euo pipefail

SCHEMA="contracts/cloudshell-fog/session-events-v0.json"

if [[ ! -f "$SCHEMA" ]]; then
  echo "ERROR: missing session event schema" >&2
  exit 1
fi

# basic JSON validity check (no jq dependency fallback)
python3 - <<EOF
import json,sys
with open("$SCHEMA") as f:
    json.load(f)
print("OK: schema valid JSON")
EOF
