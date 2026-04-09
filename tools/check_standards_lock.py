#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "standards.lock.yaml"
PLACEHOLDER_RE = re.compile(r"REPLACE_WITH_PINNED_[A-Z_]+")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _commit_values(text: str) -> list[str]:
    commits: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("commit:") or stripped.startswith("ref:"):
            _, value = stripped.split(":", 1)
            commits.append(value.strip())
    return commits


def main() -> int:
    if not LOCK.exists():
        fail("missing standards.lock.yaml")
    text = LOCK.read_text(encoding="utf-8", errors="replace")
    required = [
        "kind: StandardsLock",
        "tritrpc:",
        "ontogenesis:",
        "semantic-serdes:",
        "standards-storage:",
        "identity-prime-reference:",
        "hdt-reference:",
        "lampstand:",
    ]
    for needle in required:
        if needle not in text:
            fail(f"standards.lock.yaml missing required section: {needle}")

    if PLACEHOLDER_RE.search(text):
        fail("standards.lock.yaml still contains placeholder pin values")

    commits = _commit_values(text)
    if not commits:
        fail("standards.lock.yaml does not contain any commit/ref values")
    for value in commits:
        if not COMMIT_RE.match(value):
            fail(f"standards.lock.yaml contains non-SHA pin value: {value}")

    print("OK: standards lock structure and pin checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
