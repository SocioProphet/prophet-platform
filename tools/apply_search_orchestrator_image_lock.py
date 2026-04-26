from __future__ import annotations

import argparse
import json
from pathlib import Path

from render_search_orchestrator_image_patch import IMAGE, validate_lock, render_patch

LOCK_PATH = Path("releases/images/search-orchestrator.image-lock.json")
PATCH_PATH = Path("infra/k8s/search-orchestrator/overlays/policy/image-patch.yaml")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def build_lock(evidence: dict) -> dict:
    digest = str(evidence.get("digest", ""))
    source_sha = str(evidence.get("source_sha", ""))
    pinned_ref = str(evidence.get("pinned_ref", ""))
    lock = {
        "image_lock_id": "search-orchestrator-image-lock",
        "component": "services/search-orchestrator",
        "image": IMAGE,
        "source_sha": source_sha,
        "digest": digest,
        "pinned_ref": pinned_ref,
        "workflow": ".github/workflows/search-orchestrator-image.yml",
        "status": "pinned",
    }
    validate_lock(lock)
    return lock


def write_outputs(lock: dict, lock_path: Path, patch_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    patch_path.write_text(render_patch(str(lock["pinned_ref"])), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Search Orchestrator image digest evidence to release lock and Kustomize patch")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--lock-output", type=Path, default=LOCK_PATH)
    parser.add_argument("--patch-output", type=Path, default=PATCH_PATH)
    args = parser.parse_args()

    lock = build_lock(load_json(args.evidence))
    write_outputs(lock, args.lock_output, args.patch_output)
    print(f"wrote image lock to {args.lock_output}")
    print(f"wrote image patch to {args.patch_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
