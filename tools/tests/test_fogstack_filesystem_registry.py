from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_registry(tmp_path: Path) -> Path:
    publication_set = tmp_path / "manifest-publication-set.json"
    gate_record = tmp_path / "publication-gate.record.json"
    manifest = tmp_path / "fogstack.access-v0.1.manifest.json"
    index = tmp_path / "registry-publication.index.json"
    registry_root = tmp_path / "registry"

    write_json(publication_set, {
        "kind": "FogStackManifestPublicationSet",
        "schema_version": "v0.1",
        "manifests": [],
    })
    write_json(gate_record, {
        "kind": "FogStackReleasePublicationGateRecord",
        "schema_version": "v0.1",
        "status": "pass",
        "checks": [],
    })
    write_json(manifest, {
        "kind": "FogStackBundleManifest",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
    })

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_publication_index.py",
        "--registry-uri", "file://registry/fogstack",
        "--publication-set", str(publication_set),
        "--publication-gate-record", str(gate_record),
        "--artifact", "manifest", str(manifest),
        "--output", str(index),
    ], check=True)

    subprocess.run([
        sys.executable,
        "tools/publish_fogstack_filesystem_registry.py",
        "--index", str(index),
        "--registry-root", str(registry_root),
        "--bundle-id", "fogstack.access",
        "--version", "0.1.0",
    ], check=True)
    return registry_root


def test_publish_and_check_filesystem_registry(tmp_path: Path) -> None:
    registry_root = build_registry(tmp_path)
    release_root = registry_root / "fogstack.access" / "0.1.0"
    assert (release_root / "release-pointer.json").exists()
    assert (release_root / "registry-publication.index.json").exists()
    assert (release_root / "artifacts" / "fogstack.access-v0.1.manifest.json").exists()

    subprocess.run([
        sys.executable,
        "tools/check_fogstack_filesystem_registry.py",
        "--registry-root", str(registry_root),
        "--bundle-id", "fogstack.access",
        "--version", "0.1.0",
    ], check=True)


def test_filesystem_registry_root_build_and_check(tmp_path: Path) -> None:
    registry_root = build_registry(tmp_path)

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_filesystem_registry_root.py",
        "--registry-root", str(registry_root),
        "--registry-uri", "file://registry/fogstack",
    ], check=True)

    root_path = registry_root / "registry-root.json"
    assert root_path.exists()
    root = json.loads(root_path.read_text(encoding="utf-8"))
    assert root["kind"] == "FogStackFilesystemRegistryRoot"
    assert root["releases"][0]["bundle_id"] == "fogstack.access"
    assert root["signatures"][0]["algorithm"] == "shape-only"

    subprocess.run([
        sys.executable,
        "tools/check_fogstack_filesystem_registry_root.py",
        "--registry-root", str(registry_root),
    ], check=True)


def test_filesystem_registry_root_check_rejects_tampered_pointer(tmp_path: Path) -> None:
    registry_root = build_registry(tmp_path)
    subprocess.run([
        sys.executable,
        "tools/build_fogstack_filesystem_registry_root.py",
        "--registry-root", str(registry_root),
        "--registry-uri", "file://registry/fogstack",
    ], check=True)

    pointer = registry_root / "fogstack.access" / "0.1.0" / "release-pointer.json"
    data = json.loads(pointer.read_text(encoding="utf-8"))
    data["version"] = "0.1.1"
    write_json(pointer, data)

    proc = subprocess.run([
        sys.executable,
        "tools/check_fogstack_filesystem_registry_root.py",
        "--registry-root", str(registry_root),
    ])
    assert proc.returncode != 0


def test_filesystem_registry_check_rejects_missing_release(tmp_path: Path) -> None:
    proc = subprocess.run([
        sys.executable,
        "tools/check_fogstack_filesystem_registry.py",
        "--registry-root", str(tmp_path / "registry"),
        "--bundle-id", "fogstack.access",
        "--version", "0.1.0",
    ])
    assert proc.returncode != 0
