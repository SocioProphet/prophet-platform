#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-structural}"
PROFILE="${2:-standard}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$MODE" in
  structural)
    bash "$ROOT/tools/validate-cloudshell-fog-structural-conformance.sh"
    ;;
  upstream)
    bash "$ROOT/tools/validate-cloudshell-fog-upstream-alignment.sh"
    ;;
  release)
    bash "$ROOT/tools/validate-cloudshell-fog-release-evidence.sh"
    ;;
  governance)
    bash "$ROOT/tools/validate-cloudshell-fog-runtime-governance.sh"
    ;;
  access)
    bash "$ROOT/tools/validate-cloudshell-fog-access-profile.sh"
    ;;
  go-live)
    bash "$ROOT/tools/validate-cloudshell-fog-go-live-v2.sh" "$PROFILE"
    ;;
  platform)
    bash "$ROOT/tools/validate-cloudshell-fog-platform-conformance-v2.sh" "$PROFILE"
    ;;
  *)
    echo "Usage: $0 <structural|upstream|release|governance|access|go-live|platform> [standard|federal]" >&2
    exit 2
    ;;
esac
