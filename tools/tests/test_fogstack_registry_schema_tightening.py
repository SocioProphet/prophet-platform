"""Tests proving tightened registry root and revocation JSON Schemas behave correctly.

Valid builder output must still pass; malformed shapes must fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).parent.parent.parent / "schemas" / "release"
SHA256_A = "sha256:" + "a" * 64
SHA256_B = "sha256:" + "b" * 64
SHA256_C = "sha256:" + "c" * 64


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def validation_errors(instance: dict, schema: dict) -> list:
    validator = jsonschema.Draft202012Validator(schema)
    return list(validator.iter_errors(instance))


def is_valid(instance: dict, schema: dict) -> bool:
    return not validation_errors(instance, schema)


# ---------------------------------------------------------------------------
# Registry Root Metadata
# ---------------------------------------------------------------------------


class TestRegistryRootMetadataSchema:
    @pytest.fixture(autouse=True)
    def _load_schema(self):
        self.schema = load_schema("fogstack-registry-root-metadata-v0.1.schema.json")

    # -- valid shapes --

    def test_valid_minimal_unsigned_root(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [],
            "signed": False,
            "signature": None,
            "revocation_index_ref": None,
            "revocation_index_digest": None,
        }
        assert is_valid(instance, self.schema)

    def test_valid_root_with_release_and_revocation(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [
                {
                    "bundle_id": "fogstack.access",
                    "version": "0.1.0",
                    "release_pointer_ref": "registry/fogstack.access/0.1.0/release-pointer.json",
                    "release_pointer_digest": SHA256_A,
                    "registry_publication_index_ref": "registry/fogstack.access/0.1.0/index.json",
                    "registry_publication_index_digest": SHA256_B,
                }
            ],
            "revocation_index_ref": "registry/revocations.json",
            "revocation_index_digest": SHA256_C,
            "signed": True,
            "signature": {"type": "other", "ref": "artifact://registry/root.sig"},
        }
        assert is_valid(instance, self.schema)

    def test_valid_signed_root_with_sigstore_type(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "https://registry.example.com",
            "releases": [],
            "signed": True,
            "signature": {"type": "sigstore", "ref": "artifact://registry/root.sig"},
        }
        assert is_valid(instance, self.schema)

    # -- malformed shapes --

    def test_rejects_wrong_kind(self):
        instance = {
            "kind": "WrongKind",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [],
            "signed": False,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_missing_required_fields(self):
        # Missing 'releases' and 'signed'
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_malformed_release_pointer_digest(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [
                {
                    "bundle_id": "fogstack.access",
                    "version": "0.1.0",
                    "release_pointer_ref": "path/to/pointer.json",
                    "release_pointer_digest": "sha256:tooshort",
                    "registry_publication_index_ref": "path/to/index.json",
                    "registry_publication_index_digest": SHA256_B,
                }
            ],
            "signed": False,
            "signature": None,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_malformed_publication_index_digest(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [
                {
                    "bundle_id": "fogstack.access",
                    "version": "0.1.0",
                    "release_pointer_ref": "path/to/pointer.json",
                    "release_pointer_digest": SHA256_A,
                    "registry_publication_index_ref": "path/to/index.json",
                    "registry_publication_index_digest": "md5:wrongalg",
                }
            ],
            "signed": False,
            "signature": None,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_malformed_revocation_digest(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [],
            "revocation_index_ref": "path/to/index",
            "revocation_index_digest": "not-a-sha256",
            "signed": False,
            "signature": None,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_release_missing_bundle_id(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [
                {
                    "version": "0.1.0",
                    "release_pointer_ref": "path",
                    "release_pointer_digest": SHA256_A,
                    "registry_publication_index_ref": "path",
                    "registry_publication_index_digest": SHA256_B,
                }
            ],
            "signed": False,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_release_with_extra_properties(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [
                {
                    "bundle_id": "fogstack.access",
                    "version": "0.1.0",
                    "release_pointer_ref": "path",
                    "release_pointer_digest": SHA256_A,
                    "registry_publication_index_ref": "path",
                    "registry_publication_index_digest": SHA256_B,
                    "unknown_extra_field": "should_fail",
                }
            ],
            "signed": False,
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_root_with_extra_properties(self):
        instance = {
            "kind": "FogStackRegistryRootMetadata",
            "schema_version": "v0.1",
            "registry_uri": "file://registry",
            "releases": [],
            "signed": False,
            "unknown_top_level": "bad",
        }
        assert not is_valid(instance, self.schema)


# ---------------------------------------------------------------------------
# Revocation Index
# ---------------------------------------------------------------------------


class TestRevocationIndexSchema:
    @pytest.fixture(autouse=True)
    def _load_schema(self):
        self.schema = load_schema("fogstack-registry-revocation-index-v0.1.schema.json")

    # -- valid shapes --

    def test_valid_empty_index(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [],
        }
        assert is_valid(instance, self.schema)

    def test_valid_revoked_entry(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                    "status": "revoked",
                    "reason": "superseded",
                    "superseded_by": "fogstack.old@0.0.2",
                }
            ],
        }
        assert is_valid(instance, self.schema)

    def test_valid_rollback_entry(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                    "status": "rollback",
                    "reason": "regression",
                    "superseded_by": None,
                }
            ],
        }
        assert is_valid(instance, self.schema)

    def test_valid_entry_with_null_reason_and_superseded_by(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.access",
                    "version": "0.1.0",
                    "status": "revoked",
                    "reason": None,
                    "superseded_by": None,
                }
            ],
        }
        assert is_valid(instance, self.schema)

    # -- malformed shapes --

    def test_rejects_invalid_status(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                    "status": "suspended",
                }
            ],
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_eligible_status(self):
        # 'eligible' belongs to the rollback-revocation-index, not here
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                    "status": "eligible",
                }
            ],
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_entry_missing_status(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                }
            ],
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_wrong_kind(self):
        instance = {
            "kind": "WrongKind",
            "schema_version": "v0.1",
            "entries": [],
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_entry_with_extra_properties(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [
                {
                    "bundle_id": "fogstack.old",
                    "version": "0.0.1",
                    "status": "revoked",
                    "unknown_extra": "bad",
                }
            ],
        }
        assert not is_valid(instance, self.schema)

    def test_rejects_top_level_extra_properties(self):
        instance = {
            "kind": "FogStackRegistryRevocationIndex",
            "schema_version": "v0.1",
            "entries": [],
            "unexpected_field": True,
        }
        assert not is_valid(instance, self.schema)


# ---------------------------------------------------------------------------
# Integration: builder output conforms to tightened schemas
# ---------------------------------------------------------------------------


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_builder_revocation_index_conforms_to_schema(tmp_path: Path) -> None:
    """Output from build_fogstack_registry_revocation_index passes the tightened schema."""
    revocations = tmp_path / "revocations.json"
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_registry_revocation_index.py",
            "--entry", "fogstack.old:0.0.1:revoked:superseded:",
            "--entry", "fogstack.access:0.1.0:rollback:regression:fogstack.access@0.0.9",
            "--output", str(revocations),
        ],
        check=True,
    )
    data = json.loads(revocations.read_text(encoding="utf-8"))
    schema = load_schema("fogstack-registry-revocation-index-v0.1.schema.json")
    assert is_valid(data, schema), validation_errors(data, schema)


def test_builder_registry_root_metadata_conforms_to_schema(tmp_path: Path) -> None:
    """Output from build_fogstack_registry_root_metadata passes the tightened schema."""
    release_root = tmp_path / "registry" / "fogstack.access" / "0.1.0"
    pointer = release_root / "release-pointer.json"
    index = release_root / "registry-publication.index.json"
    revocations = tmp_path / "revocations.json"
    root_out = tmp_path / "registry-root.json"

    write_json(pointer, {
        "kind": "FogStackFilesystemRegistryReleasePointer",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "index_ref": str(index),
        "index_digest": SHA256_A,
    })
    write_json(index, {
        "kind": "FogStackRegistryPublicationIndex",
        "schema_version": "v0.1",
        "registry_uri": "file://registry",
        "artifacts": [],
    })

    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_registry_revocation_index.py",
            "--entry", "fogstack.old:0.0.1:revoked:superseded:",
            "--output", str(revocations),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "tools/build_fogstack_registry_root_metadata.py",
            "--registry-uri", "file://registry",
            "--release", "fogstack.access", "0.1.0", str(release_root),
            "--revocation-index", str(revocations),
            "--signature-type", "other",
            "--signature-ref", "artifact://registry/root.sig",
            "--output", str(root_out),
        ],
        check=True,
    )

    data = json.loads(root_out.read_text(encoding="utf-8"))
    schema = load_schema("fogstack-registry-root-metadata-v0.1.schema.json")
    assert is_valid(data, schema), validation_errors(data, schema)
