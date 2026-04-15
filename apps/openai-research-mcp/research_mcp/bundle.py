from __future__ import annotations

from pathlib import Path

REQUIRED_RELATIVE_FILES = (
    "README.md",
    "server.py",
    "pyproject.toml",
    "research_mcp/__init__.py",
    "research_mcp/models.py",
    "research_mcp/errors.py",
    "research_mcp/auth.py",
    "research_mcp/store.py",
    "research_mcp/service.py",
    "research_mcp/artifacts.py",
    "research_mcp/audit.py",
    "config/static_tokens.example.json",
    "config/openai_responses_config.example.json",
    "data/example_documents.json",
    "tests/test_smoke.py",
)


def bundle_integrity_report(root: str | Path) -> dict:
    root = Path(root)
    present = []
    missing = []
    for rel in REQUIRED_RELATIVE_FILES:
        if (root / rel).exists():
            present.append(rel)
        else:
            missing.append(rel)
    return {
        "root": str(root),
        "required_files": list(REQUIRED_RELATIVE_FILES),
        "present": present,
        "missing": missing,
        "ok": not missing,
    }
