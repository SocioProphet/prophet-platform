#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMA="$ROOT/contracts/cloudshell-fog/deployment-inventory-v0.json"
EXAMPLE="$ROOT/apps/cloudshell-fog/deployment-inventory.example.yaml"
DOC="$ROOT/docs/CLOUDSHELL_FOG_SECRETS_AND_IMAGES_V0.md"

for f in "$SCHEMA" "$EXAMPLE" "$DOC"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    exit 1
  fi
done

python3 - <<EOF
import json, sys
with open("$SCHEMA") as f:
    json.load(f)
print("OK: deployment inventory schema valid JSON")
EOF

echo "OK: cloudshell-fog inventory assets present"
