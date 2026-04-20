#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export SOCIOPROFIT_STATE_HOME="$TMP/state"
export PYTHONPATH="$ROOT/apps/lampstand/src"

mkdir -p "$TMP/input"
cat > "$TMP/input/sample.txt" <<'EOF'
Prophet Platform vertical slice sample
EOF

python3 -m prophet_platform_lampstand.main ingest \
  --path "$TMP/input/sample.txt" \
  --scope-ref "scope://local/default" \
  --zone-ref "zone://edge" \
  --topic-ref "zone.edge.carrier.ingested.v1" \
  --classifier "slice:phase4" \
  --classifier "service:lampstand"

python3 -m prophet_platform_lampstand.main discover --limit 5
