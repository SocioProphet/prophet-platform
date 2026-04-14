#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMA="$ROOT/contracts/cloudshell-fog/production-decision-record-v0.json"
STD="$ROOT/apps/cloudshell-fog/production-decision-record.standard.example.yaml"
FED="$ROOT/apps/cloudshell-fog/production-decision-record.federal.example.yaml"

for f in "$SCHEMA" "$STD" "$FED"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    exit 1
  fi
done

python3 - <<EOF
import json
with open("$SCHEMA") as f:
    json.load(f)
print("OK: production decision record schema valid JSON")
EOF

echo "OK: cloudshell-fog decision record assets present"
