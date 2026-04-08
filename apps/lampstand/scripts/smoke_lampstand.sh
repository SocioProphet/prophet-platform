#!/usr/bin/env bash
set -euo pipefail

python3 -m prophet_platform_lampstand.main doctor || true
python3 -m prophet_platform_lampstand.main emit-receipt \
  --event-type lampstand.smoke \
  --action Smoke \
  --status succeeded \
  --subject-ref service://lampstand \
  --payload-ref artifact://smoke
