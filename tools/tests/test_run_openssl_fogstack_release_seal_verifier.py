from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_openssl_release_seal_verifier(tmp_path: Path) -> None:
    seal = tmp_path / "release.seal.json"
    sig = tmp_path / "release.seal.sig"
    priv = tmp_path / "private.pem"
    pub = tmp_path / "public.pem"
    out = tmp_path / "verify.json"

    _write_json(
        seal,
        {
            "kind": "FogStackReleaseSeal",
            "schema_version": "v0.1",
            "bundle_id": "fogstack.access",
            "version": "0.1.0",
            "algorithm": "sha256",
            "release_root_hash": "sha256:test-seal-root",
            "artifact_hashes": [],
            "signed": True,
            "signature": {"type": "other", "ref": str(sig)},
        },
    )

    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(priv)], check=True)
    subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout", "-out", str(pub)], check=True)
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(priv), "-out", str(sig), str(seal)], check=True)

    cmd = [
        sys.executable,
        "tools/run_openssl_fogstack_release_seal_verifier.py",
        "--seal",
        str(seal),
        "--signature",
        str(sig),
        "--public-key",
        str(pub),
        "--output",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    data = _read_json(out)
    assert data["status"] == "pass"
    assert data["verified_root_hash"] == "sha256:test-seal-root"
