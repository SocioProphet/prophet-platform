#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "apps",
    "infra",
    "docs",
]

SUSPECT_PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bPLACEHOLDER\b",
    r"\n\.\.\.\n",
]

def fail(msg: str) -> "None":
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)

def main() -> int:
    # Directory requirements
    for d in REQUIRED_DIRS:
        if not (ROOT / d).exists():
            fail(f"missing required directory: {d}")

    # No .DS_Store
    ds = list(ROOT.rglob(".DS_Store"))
    if ds:
        fail(f"found .DS_Store files: {len(ds)} — remove and add to .gitignore")

    # Lightweight doc sanity: no obvious placeholders in top-level docs
    doc_candidates = []
    for rel in ("docs/ARCHITECTURE.md", "docs/SECURITY.md", "docs/TRITRPC_SPEC.md", "docs/ROADMAP.md"):
        p = ROOT / rel
        if p.exists():
            doc_candidates.append(p)

    for p in doc_candidates:
        s = p.read_text(encoding="utf-8", errors="replace")
        for pat in SUSPECT_PLACEHOLDER_PATTERNS:
            if re.search(pat, s, flags=re.IGNORECASE):
                fail(f"doc looks unfinished (matches {pat!r}): {p.relative_to(ROOT)}")

    # Ensure infra landing exists if infra/k8s present
    if (ROOT / "infra/k8s").exists() and not (ROOT / "infra/README.md").exists():
        # not fatal, but warn loudly
        print("WARN: infra/k8s exists but infra/README.md missing (recommended)")

    print("OK: validate passed (required dirs present, no .DS_Store, docs look non-placeholder)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
