#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = ROOT / "contracts/computational-artifacts/prophet-artifact.v1alpha1.example.yaml"

from prophet_artifact_contract import ValidationError, load_manifest, stable_run_id, validate_manifest  # noqa: E402


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a ProphetArtifact v1alpha1 manifest")
    parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT), help="Path to prophet-artifact.yaml")
    args = parser.parse_args()

    path = Path(args.artifact).expanduser()
    if not path.is_absolute():
        path = ROOT / path

    try:
        manifest = load_manifest(path)
        parsed = validate_manifest(manifest)
    except ValidationError as exc:
        fail(str(exc))

    output = {
        "ok": True,
        "artifact": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
        "run_id": stable_run_id(manifest),
        "metadata": {
            "name": parsed["metadata"]["name"],
            "version": parsed["metadata"]["version"],
        },
        "supported_verbs": [action["verb"] for action in parsed["actions"]],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
