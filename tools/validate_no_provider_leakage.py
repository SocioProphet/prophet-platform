#!/usr/bin/env python3
"""
Rejects provider-specific names in canonical contracts and schemas.
Provider specifics belong in infra/tofu/envs/* and adapter modules — not contracts.

Governed by the provider-agnostic constraint established in design review.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Directories that contain canonical contracts — must not have provider leakage
CANONICAL_DIRS = [
    ROOT / "contracts",
    ROOT / "schemas",
    ROOT / "specs",
]

# Directories explicitly allowed to contain provider names
EXEMPT_DIRS = [
    ROOT / "infra" / "tofu",
    ROOT / "infra" / "k8s",
    ROOT / "infra" / "local",
    ROOT / "infra" / "argocd",
]

# Provider-specific tokens that must not appear in canonical contract files
BANNED_PATTERNS = [
    # Cloud provider names as significant identifiers (not in prose/comments)
    r'"gcp"',
    r'"aws"',
    r'"azure"',
    r'"gcs://',
    r'"s3://',
    r'"az://',
    r'"us-central1"',
    r'"us-east1"',
    r'"us-west1"',
    r'"europe-west',
    r'"asia-east',
    r'googleapis\.com',
    r'\.amazonaws\.com',
    r'\.blob\.core\.windows\.net',
    r'"google_',
    r'"aws_',
    r'"azurerm_',
]

COMPILED = [re.compile(p) for p in BANNED_PATTERNS]

ERRORS: list[tuple[Path, int, str, str]] = []

FILE_EXTENSIONS = {".json", ".yaml", ".yml"}


def is_exempt(path: Path) -> bool:
    for exempt in EXEMPT_DIRS:
        try:
            path.relative_to(exempt)
            return True
        except ValueError:
            pass
    return False


def check_file(path: Path) -> None:
    if is_exempt(path):
        return
    if path.suffix not in FILE_EXTENSIONS:
        return

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comment lines
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue
        for pattern in COMPILED:
            if pattern.search(line):
                ERRORS.append((path, lineno, pattern.pattern, line.rstrip()))


def main() -> None:
    print("=== validate-no-provider-leakage ===")

    checked = 0
    for scan_dir in CANONICAL_DIRS:
        if not scan_dir.exists():
            continue
        for path in sorted(scan_dir.rglob("*")):
            if path.is_file():
                check_file(path)
                checked += 1

    if ERRORS:
        print(f"\n{len(ERRORS)} provider-leakage violation(s) found:\n")
        for path, lineno, pattern, line in ERRORS:
            rel = path.relative_to(ROOT)
            print(f"  {rel}:{lineno}  [{pattern}]")
            print(f"    {line[:120]}")
        print(
            "\nProvider-specific names belong in infra/tofu/envs/* "
            "or adapter modules — not canonical contracts."
        )
        sys.exit(1)
    else:
        print(f"  OK  {checked} files checked — no provider leakage detected.")


if __name__ == "__main__":
    main()
