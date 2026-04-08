#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
API_K = ROOT / "apps/api/kustomize/base/kustomization.yaml"
GW_K = ROOT / "apps/gateway/kustomize/base/kustomization.yaml"
API_DEP = ROOT / "apps/api/kustomize/base/deployment.yaml"
GW_DEP = ROOT / "apps/gateway/kustomize/base/deployment.yaml"


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    api_k = API_K.read_text(encoding="utf-8", errors="replace")
    gw_k = GW_K.read_text(encoding="utf-8", errors="replace")
    api_dep = API_DEP.read_text(encoding="utf-8", errors="replace")
    gw_dep = GW_DEP.read_text(encoding="utf-8", errors="replace")

    if "unix://" in gw_k and "tcp://" not in gw_k:
        fail("gateway base kustomization still targets unix:// only; this is invalid for separate-deployment cluster bootstrap")

    if "emptyDir" in api_dep and "emptyDir" in gw_dep and "unix://" in api_k and "unix://" in gw_k:
        fail("API and gateway both look like separate emptyDir-based deployments using unix:// only; shared socket assumption is broken")

    print("OK: transport topology checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
