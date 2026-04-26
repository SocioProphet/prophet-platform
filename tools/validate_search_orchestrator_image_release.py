from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "services/search-orchestrator/Dockerfile",
    ".github/workflows/search-orchestrator-image.yml",
    ".github/workflows/search-orchestrator-image-pin.yml",
    "releases/images/search-orchestrator.image-lock.example.json",
    "tools/render_search_orchestrator_image_patch.py",
    "tools/apply_search_orchestrator_image_lock.py",
]

REQUIRED_TEXT = {
    "services/search-orchestrator/Dockerfile": [
        "FROM python:3.12-slim",
        "USER 10001:10001",
        "uvicorn",
    ],
    ".github/workflows/search-orchestrator-image.yml": [
        "docker/build-push-action",
        "ghcr.io/socioprophet/prophet-platform/search-orchestrator",
        "steps.build.outputs.digest",
        "search-orchestrator-image-evidence",
    ],
    ".github/workflows/search-orchestrator-image-pin.yml": [
        "workflow_run",
        "search-orchestrator-image",
        "download-artifact",
        "apply_search_orchestrator_image_lock.py",
    ],
    "releases/images/search-orchestrator.image-lock.example.json": [
        "search-orchestrator-image-lock-example",
        "pinned_ref",
        "sha256:REPLACE_WITH_IMAGE_DIGEST",
    ],
    "tools/render_search_orchestrator_image_patch.py": [
        "Render a digest-pinned Search Orchestrator deployment patch",
        "pinned_ref",
        "Deployment",
    ],
    "tools/apply_search_orchestrator_image_lock.py": [
        "Apply Search Orchestrator image digest evidence",
        "image-lock.json",
        "image-patch.yaml",
    ],
}


def main() -> int:
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"missing required image artifact: {rel}")
        if not path.read_text(encoding="utf-8").strip():
            raise SystemExit(f"empty image artifact: {rel}")

    for rel, terms in REQUIRED_TEXT.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for term in terms:
            if term not in text:
                raise SystemExit(f"{rel} missing required term {term}")

    lock = json.loads((ROOT / "releases/images/search-orchestrator.image-lock.example.json").read_text(encoding="utf-8"))
    if not str(lock.get("pinned_ref", "")).startswith("ghcr.io/socioprophet/prophet-platform/search-orchestrator@sha256:"):
        raise SystemExit("image lock pinned_ref must use digest form")

    print("search-orchestrator image release artifacts validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
