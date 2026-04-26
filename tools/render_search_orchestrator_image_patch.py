from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")
IMAGE = "ghcr.io/socioprophet/prophet-platform/search-orchestrator"


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def validate_lock(lock: dict) -> str:
    digest = str(lock.get("digest", ""))
    pinned_ref = str(lock.get("pinned_ref", ""))
    if not DIGEST_RE.match(digest):
        raise SystemExit("image lock digest must be sha256:<64 hex chars>")
    expected = f"{IMAGE}@{digest}"
    if pinned_ref != expected:
        raise SystemExit(f"image lock pinned_ref must equal {expected}")
    return pinned_ref


def render_patch(pinned_ref: str) -> str:
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: search-orchestrator
spec:
  template:
    spec:
      containers:
        - name: search-orchestrator
          image: {pinned_ref}
          imagePullPolicy: IfNotPresent
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a digest-pinned Search Orchestrator deployment patch from an image lock")
    parser.add_argument("--image-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pinned_ref = validate_lock(load_json(args.image_lock))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_patch(pinned_ref), encoding="utf-8")
    print(f"wrote digest-pinned deployment patch to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
