#!/usr/bin/env python3
"""Check the OSM Map API OpenAPI contract.

The check proves that required paths/methods exist and that the generated
OpenAPI document still exposes key safety/attribution vocabulary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from osm_map_api.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "openapi/required-paths.v0.json"
EXPORT = ROOT / "openapi/generated.openapi.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        fail(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"top-level object required: {path}")
    return value


def main() -> int:
    contract = read_json(CONTRACT)
    app = create_app()
    openapi = app.openapi()

    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        fail("OpenAPI paths object missing")

    for requirement in contract.get("required_paths", []):
        path = requirement["path"]
        method = requirement["method"].lower()
        if path not in paths:
            fail(f"required OpenAPI path missing: {path}")
        if method not in paths[path]:
            fail(f"required OpenAPI method missing: {method.upper()} {path}")

    encoded = json.dumps(openapi, sort_keys=True)
    for term in contract.get("required_safety_terms", []):
        if term not in encoded:
            fail(f"required OpenAPI safety/attribution term missing: {term}")

    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    EXPORT.write_text(json.dumps(openapi, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OpenAPI contract passed; wrote {EXPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
