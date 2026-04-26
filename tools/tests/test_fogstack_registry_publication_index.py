from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_build_and_check_registry_publication_index(tmp_path: Path) -> None:
    publication_set = tmp_path / "manifest-publication-set.json"
    gate_record = tmp_path / "publication-gate.record.json"
    manifest = tmp_path / "fogstack.access-v0.1.manifest.json"
    index = tmp_path / "registry-publication.index.json"

    _write_json(publication_set, {
        "kind": "FogStackManifestPublicationSet",
        "schema_version": "v0.1",
        "manifests": [
            {"bundle_id": "fogstack.access", "version": "0.1.0", "ref": str(manifest), "signed": False}
        ],
    })
    _write_json(gate_record, {
        "kind": "FogStackReleasePublicationGateRecord",
        "schema_version": "v0.1",
        "status": "pass",
        "checks": [],
    })
    _write_json(manifest, {
        "kind": "FogStackBundleManifest",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
    })

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_publication_index.py",
        "--registry-uri", "artifact://ci/fogstack-registry",
        "--publication-set", str(publication_set),
        "--publication-gate-record", str(gate_record),
        "--artifact", "manifest", str(manifest),
        "--output", str(index),
    ], check=True)

    data = json.loads(index.read_text(encoding="utf-8"))
    assert data["kind"] == "FogStackRegistryPublicationIndex"
    assert data["registry_uri"] == "artifact://ci/fogstack-registry"
    assert data["publication_set_digest"].startswith("sha256:")
    assert data["publication_gate_record_digest"].startswith("sha256:")
    assert data["artifacts"][0]["digest"].startswith("sha256:")

    subprocess.run([
        sys.executable,
        "tools/check_fogstack_registry_publication_index.py",
        "--index", str(index),
    ], check=True)


def test_check_registry_publication_index_rejects_failed_gate(tmp_path: Path) -> None:
    publication_set = tmp_path / "manifest-publication-set.json"
    gate_record = tmp_path / "publication-gate.record.json"
    artifact = tmp_path / "artifact.json"
    index = tmp_path / "registry-publication.index.json"

    _write_json(publication_set, {"kind": "FogStackManifestPublicationSet", "schema_version": "v0.1", "manifests": []})
    _write_json(gate_record, {"kind": "FogStackReleasePublicationGateRecord", "status": "fail", "checks": []})
    _write_json(artifact, {"kind": "Artifact"})

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_publication_index.py",
        "--registry-uri", "artifact://ci/fogstack-registry",
        "--publication-set", str(publication_set),
        "--publication-gate-record", str(gate_record),
        "--artifact", "artifact", str(artifact),
        "--output", str(index),
    ], check=False)

    # Builder must reject a failed publication gate and avoid producing a usable index.
    assert not index.exists()
