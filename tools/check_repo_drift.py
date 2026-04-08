#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def check_contains(path: str, needle: str, *, should_contain: bool = True) -> None:
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    ok = needle in text
    if should_contain and not ok:
        fail(f"expected {path} to contain: {needle}")
    if not should_contain and ok:
        fail(f"unexpected drift in {path}: found forbidden text {needle!r}")


def main() -> int:
    check_contains("README.md", "contracts/")
    check_contains("README.md", "standards.lock.yaml")
    check_contains("README.md", "`rpc/`", should_contain=False)
    check_contains("README.md", "`schemas/`", should_contain=False)

    check_contains("apps/api/go.mod", "prophet-platform/apps/api")
    check_contains("apps/gateway/go.mod", "prophet-platform/apps/gateway")
    check_contains(
        "infra/k8s/argo-cd/appsets/socioprophet-appset.yaml",
        "https://github.com/SocioProphet/prophet-platform.git",
    )
    check_contains(
        "docs/TRITRPC_SPEC.md",
        "ChaCha20-Poly1305 or AES-256-GCM",
        should_contain=False,
    )
    print("OK: repo drift checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
