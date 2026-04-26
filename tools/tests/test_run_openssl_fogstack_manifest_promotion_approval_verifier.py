from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_openssl_promotion_approval_verifier_accepts_valid_signature(tmp_path: Path) -> None:
    if not shutil.which("openssl"):
        pytest.skip("openssl is not available")

    approval = tmp_path / "approval.record.json"
    approval.write_text(json.dumps({"kind": "FogStackManifestPromotionApprovalRecord"}, indent=2) + "\n", encoding="utf-8")
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    signature = tmp_path / "approval.sig"
    output = tmp_path / "verification.json"

    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(private_key)], check=True)
    subprocess.run(["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)], check=True)
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(signature), str(approval)], check=True)

    subprocess.run([
        sys.executable,
        "tools/run_openssl_fogstack_manifest_promotion_approval_verifier.py",
        "--approval-record", str(approval),
        "--signature", str(signature),
        "--public-key", str(public_key),
        "--key-ref", str(public_key),
        "--output", str(output),
    ], check=True)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["status"] == "pass"
    assert data["verification_tool"] == "openssl"
    assert data["approval_record_digest"].startswith("sha256:")
