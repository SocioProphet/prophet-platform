#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Fog Stack registry publication index")
    parser.add_argument("--registry-uri", required=True)
    parser.add_argument("--publication-set", required=True, type=Path)
    parser.add_argument("--publication-gate-record", required=True, type=Path)
    parser.add_argument("--artifact", action="append", nargs=2, metavar=("KIND", "PATH"), required=True)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    publication_set = load_json(args.publication_set)
    if publication_set.get("kind") != "FogStackManifestPublicationSet":
        raise SystemExit("ERR: publication set kind mismatch")

    gate = load_json(args.publication_gate_record)
    if gate.get("kind") != "FogStackReleasePublicationGateRecord":
        raise SystemExit("ERR: publication gate record kind mismatch")
    if gate.get("status") != "pass":
        raise SystemExit("ERR: publication gate did not pass")

    artifacts = []
    for kind, path_str in args.artifact:
        path = Path(path_str)
        artifacts.append({"kind": kind, "ref": str(path), "digest": sha256_file(path)})

    index = {
        "kind": "FogStackRegistryPublicationIndex",
        "schema_version": "v0.1",
        "registry_uri": args.registry_uri,
        "publication_set_ref": str(args.publication_set),
        "publication_set_digest": sha256_file(args.publication_set),
        "publication_gate_record_ref": str(args.publication_gate_record),
        "publication_gate_record_digest": sha256_file(args.publication_gate_record),
        "artifacts": artifacts,
        "notes": args.notes,
    }

    text = json.dumps(index, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
