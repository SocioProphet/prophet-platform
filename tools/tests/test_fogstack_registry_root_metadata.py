from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_build_and_check_registry_root_metadata(tmp_path: Path) -> None:
    release_root = tmp_path / "registry" / "fogstack.access" / "0.1.0"
    pointer = release_root / "release-pointer.json"
    index = release_root / "registry-publication.index.json"
    revocations = tmp_path / "revocations.json"
    root = tmp_path / "registry-root.json"

    write_json(pointer, {
        "kind": "FogStackFilesystemRegistryReleasePointer",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "index_ref": str(index),
        "index_digest": "sha256:test",
    })
    write_json(index, {
        "kind": "FogStackRegistryPublicationIndex",
        "schema_version": "v0.1",
        "registry_uri": "file://registry",
        "artifacts": [],
    })

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_revocation_index.py",
        "--entry", "fogstack.old:0.0.1:revoked:superseded:",
        "--output", str(revocations),
    ], check=True)

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_root_metadata.py",
        "--registry-uri", "file://registry",
        "--release", "fogstack.access", "0.1.0", str(release_root),
        "--revocation-index", str(revocations),
        "--signature-type", "other",
        "--signature-ref", "artifact://registry/root.sig",
        "--output", str(root),
    ], check=True)

    data = json.loads(root.read_text(encoding="utf-8"))
    assert data["kind"] == "FogStackRegistryRootMetadata"
    assert data["signed"] is True
    assert data["releases"][0]["release_pointer_digest"].startswith("sha256:")
    assert data["revocation_index_digest"].startswith("sha256:")

    subprocess.run([
        sys.executable,
        "tools/check_fogstack_registry_root_metadata.py",
        "--root", str(root),
        "--require-signed",
    ], check=True)


def test_registry_root_checker_rejects_bad_pointer_digest(tmp_path: Path) -> None:
    release_root = tmp_path / "registry" / "fogstack.access" / "0.1.0"
    pointer = release_root / "release-pointer.json"
    index = release_root / "registry-publication.index.json"
    root = tmp_path / "registry-root.json"

    write_json(pointer, {"kind": "pointer"})
    write_json(index, {"kind": "index"})
    write_json(root, {
        "kind": "FogStackRegistryRootMetadata",
        "schema_version": "v0.1",
        "registry_uri": "file://registry",
        "signed": True,
        "signature": {"type": "other", "ref": "artifact://registry/root.sig"},
        "releases": [
            {
                "bundle_id": "fogstack.access",
                "version": "0.1.0",
                "release_pointer_ref": str(pointer),
                "release_pointer_digest": "sha256:wrong",
                "registry_publication_index_ref": str(index),
                "registry_publication_index_digest": "sha256:wrong",
            }
        ],
    })

    proc = subprocess.run([
        sys.executable,
        "tools/check_fogstack_registry_root_metadata.py",
        "--root", str(root),
        "--require-signed",
    ])
    assert proc.returncode != 0


def test_revocation_index_checker_rejects_duplicates(tmp_path: Path) -> None:
    revocations = tmp_path / "revocations.json"
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_revocation_index.py",
        "--entry", "fogstack.access:0.1.0:revoked:first:",
        "--entry", "fogstack.access:0.1.0:rollback:duplicate:fogstack.access@0.0.9",
        "--output", str(revocations),
    ], check=True)

    proc = subprocess.run([
        sys.executable,
        "tools/check_fogstack_registry_revocation_index.py",
        "--index", str(revocations),
    ])
    assert proc.returncode != 0
