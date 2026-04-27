#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
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


def canonical_digest(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def release_entry(registry_root: Path, release_ref: str, status: str, reason: str) -> dict[str, Any]:
    release_root = registry_root / release_ref
    pointer_path = release_root / "release-pointer.json"
    if not pointer_path.exists():
        raise SystemExit(f"ERR: release pointer missing: {pointer_path}")
    pointer = load_json(pointer_path)
    bundle_id = pointer.get("bundle_id")
    version = pointer.get("version")
    if not isinstance(bundle_id, str) or not isinstance(version, str):
        raise SystemExit(f"ERR: malformed release pointer identity: {pointer_path}")
    return {
        "bundle_id": bundle_id,
        "version": version,
        "pointer_ref": str(pointer_path.relative_to(registry_root)),
        "pointer_digest": sha256_file(pointer_path),
        "status": status,
        "reason": reason,
    }


def revoked_entry(registry_root: Path, release_ref: str, status: str, reason: str) -> dict[str, Any]:
    entry = release_entry(registry_root, release_ref, status="deprecated", reason=reason)
    entry.pop("status")
    entry["revocation_status"] = status
    entry["effective_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Fog Stack registry rollback/revocation index")
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--registry-uri", required=True)
    parser.add_argument("--rollback-target", action="append", default=[], help="release path relative to registry root, for example fogstack.access/0.1.0")
    parser.add_argument("--preferred-rollback-target", action="append", default=[], help="preferred rollback release path relative to registry root")
    parser.add_argument("--revoke", action="append", default=[], help="revoked release path relative to registry root")
    parser.add_argument("--suspend", action="append", default=[], help="suspended release path relative to registry root")
    parser.add_argument("--reason", default="operator-specified registry lifecycle state")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--key-id", default="shape-only-registry-lifecycle-key")
    parser.add_argument("--signature-ref", default="shape-only://fogstack/registry-rollback-revocation-index")
    args = parser.parse_args()

    if not args.registry_root.exists():
        raise SystemExit(f"ERR: registry root missing: {args.registry_root}")

    rollback_targets: list[dict[str, Any]] = []
    for ref in args.rollback_target:
        rollback_targets.append(release_entry(args.registry_root, ref, "eligible", args.reason))
    for ref in args.preferred_rollback_target:
        rollback_targets.append(release_entry(args.registry_root, ref, "preferred", args.reason))

    revocations: list[dict[str, Any]] = []
    for ref in args.revoke:
        revocations.append(revoked_entry(args.registry_root, ref, "revoked", args.reason))
    for ref in args.suspend:
        revocations.append(revoked_entry(args.registry_root, ref, "suspended", args.reason))

    index: dict[str, Any] = {
        "kind": "FogStackRegistryRollbackRevocationIndex",
        "schema_version": "v0.1",
        "registry_uri": args.registry_uri,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rollback_targets": rollback_targets,
        "revocations": revocations,
        "signatures": [
            {
                "key_id": args.key_id,
                "algorithm": "shape-only",
                "signature_ref": args.signature_ref,
            }
        ],
    }
    digest_material = dict(index)
    digest_material["index_digest"] = None
    index["index_digest"] = canonical_digest(digest_material)

    output = args.output or (args.registry_root / "rollback-revocation.index.json")
    output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
