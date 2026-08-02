#!/usr/bin/env python3
"""Shared helpers for the program-board reconciler + parity drill.

The source of truth is sociosphere's registry/board-spec.yaml. GitHub Projects
(and any sovereign board surface) are RENDER TARGETS converged from it. These
helpers load the spec and read actual GitHub Project state via `gh`; the pure
diff logic lives in board_parity_drill.compute_drift so it is unit-testable
offline (no network) — see tools/tests/test_board_parity_drill.py.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required (pip install pyyaml)") from exc


def load_spec(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or data.get("boards") is None:
        raise SystemExit(f"{path}: not a board-spec (no 'boards')")
    return data


def boards_with_items(spec: dict) -> list[dict]:
    """Spec boards that declare at least one issue item (the ones a drill checks)."""
    return [b for b in spec["boards"] if b.get("items")]


def sh(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def project_issue_numbers(owner: str, number: int) -> set[int]:
    """Issue numbers currently present as items on a GitHub Project (via gh)."""
    rc, out, err = sh(
        ["gh", "project", "item-list", str(number), "--owner", owner,
         "--format", "json", "--limit", "300"]
    )
    if rc != 0:
        raise SystemExit(f"gh project item-list {owner}#{number} failed: {err}")
    items = json.loads(out).get("items", []) if out else []
    return {
        (it.get("content") or {}).get("number")
        for it in items
        if (it.get("content") or {}).get("number") is not None
    }
