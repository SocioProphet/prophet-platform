from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_mcp.bundle import bundle_integrity_report

print(json.dumps(bundle_integrity_report(ROOT), indent=2, sort_keys=True))
