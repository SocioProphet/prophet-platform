#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach signature metadata to a Fog Stack bundle manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--signature-type", required=True, choices=["cosign", "sigstore", "other"])
    parser.add_argument("--signature-ref", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    manifest["signed"] = True
    manifest["signature"] = {
        "type": args.signature_type,
        "ref": args.signature_ref,
    }

    text = json.dumps(manifest, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
