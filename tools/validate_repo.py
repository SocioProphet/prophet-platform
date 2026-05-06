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


def run_optional_validator(path: str, failure_message: str) -> None:
    validator = ROOT / path
    if validator.exists():
        result = subprocess.run([sys.executable, str(validator)], cwd=ROOT, check=False)
        if result.returncode != 0:
            fail(failure_message)


def run_professional_intelligence_validation() -> None:
    run_optional_validator("tools/validate_professional_intelligence.py", "Professional Intelligence validation failed")


def run_personal_intelligence_cell_validation() -> None:
    run_optional_validator("tools/validate_personal_intelligence_cell.py", "Personal Intelligence Cell validation failed")


def run_cell_lampstand_adapter_validation() -> None:
    run_optional_validator("tools/validate_cell_lampstand_adapter.py", "Cell Lampstand adapter validation failed")


def run_cell_postgres_runtime_validation() -> None:
    run_optional_validator("tools/validate_cell_postgres_runtime.py", "Cell Postgres runtime validation failed")


def run_cell_clickhouse_fact_validation() -> None:
    run_optional_validator("tools/validate_cell_clickhouse_facts.py", "Cell ClickHouse fact validation failed")


def run_cell_gateway_api_validation() -> None:
    run_optional_validator("tools/validate_cell_gateway_api.py", "Cell gateway API validation failed")


def run_prophet_understand_validation() -> None:
    run_optional_validator("tools/validate_prophet_understand.py", "Prophet Understand repo intelligence validation failed")


def run_prophet_understand_vertical_slice() -> None:
    run_optional_validator("tools/run_prophet_understand_vertical_slice.py", "Prophet Understand vertical slice failed")


def run_cell_service_smoke() -> None:
    run_optional_validator("tools/smoke_cell_service_loop.py", "Cell service loop smoke failed")


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
run_cell_lampstand_adapter_validation()
run_cell_postgres_runtime_validation()
run_cell_clickhouse_fact_validation()
run_cell_gateway_api_validation()
run_prophet_understand_validation()
run_prophet_understand_vertical_slice()
run_cell_service_smoke()

print("OK: validate passed")
