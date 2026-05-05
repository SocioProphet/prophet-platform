#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRS = ["apps", "infra", "docs", "contracts", "tools"]
REQUIRED_FILES = [
    "go.work",
    "docs/ARCHITECTURE.md",
    "docs/TRITRPC_SPEC.md",
    "docs/TRITRPC_PLATFORM_BINDING.md",
    "apps/api/go.mod",
    "apps/gateway/go.mod",
    "contracts/imported/IMPORT_MANIFEST.yaml",
    "docs/ZONE_MODEL.md",
    "docs/DROPZONE_MEMBRANES.md",
    "docs/EVENT_BUS_TOPICS.md",
    "docs/MEMORY_MESH_INTEGRATION.md",
]
SUSPECT_PATTERNS = [r"\bTODO\b", r"\bPLACEHOLDER\b", r"\n\.\.\.\n"]


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def run_professional_intelligence_validation() -> None:
    validator = ROOT / "tools/validate_professional_intelligence.py"
    if validator.exists():
        result = subprocess.run([sys.executable, str(validator)], cwd=ROOT, check=False)
        if result.returncode != 0:
            fail("Professional Intelligence validation failed")


def run_personal_intelligence_cell_validation() -> None:
    validator = ROOT / "tools/validate_personal_intelligence_cell.py"
    if validator.exists():
        result = subprocess.run([sys.executable, str(validator)], cwd=ROOT, check=False)
        if result.returncode != 0:
            fail("Personal Intelligence Cell validation failed")


for rel in REQUIRED_DIRS:
    if not (ROOT / rel).exists():
        fail(f"missing required directory: {rel}")

for rel in REQUIRED_FILES:
    if not (ROOT / rel).exists():
        fail(f"missing required file: {rel}")

for rel in ["README.md", "docs/ARCHITECTURE.md", "docs/TRITRPC_SPEC.md", "docs/TRITRPC_PLATFORM_BINDING.md", "docs/ZONE_MODEL.md"]:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    for pat in SUSPECT_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            fail(f"document looks unfinished ({pat!r}): {rel}")

readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
if "`rpc/`" in readme:
    fail("README still refers to legacy rpc path")

appset = (ROOT / "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml").read_text(encoding="utf-8", errors="replace")
if "socioprophet/socioprophet.git" in appset:
    fail("Argo appset still points at legacy socioprophet repo")

for gomod in [ROOT / "apps/api/go.mod", ROOT / "apps/gateway/go.mod"]:
    text = gomod.read_text(encoding="utf-8", errors="replace")
    if "socioprophet/apps" in text:
        fail(f"legacy module path remains in {gomod.relative_to(ROOT)}")

for rel in [
    "contracts/imported/semantic-serdes/SOURCE_MANIFEST.yaml",
    "contracts/imported/new-hope/SOURCE_MANIFEST.yaml",
    "contracts/imported/memory-mesh/SOURCE_MANIFEST.yaml",
]:
    if not (ROOT / rel).exists():
        fail(f"missing imported source manifest: {rel}")

run_professional_intelligence_validation()
run_personal_intelligence_cell_validation()

print("OK: validate passed")
