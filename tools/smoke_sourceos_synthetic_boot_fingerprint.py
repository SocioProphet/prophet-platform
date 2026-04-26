#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected object in {path}")
    return data


def main() -> int:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof_dir = tmp_path / "proof"
        generated_boot_release = tmp_path / "boot-release-set.from-nlboot.json"
        boot_plan = tmp_path / "nlboot-plan.json"
        fingerprint = tmp_path / "synthetic-boot-fingerprint.json"

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "build_sourceos_m2_lifecycle_proof.py"),
            "--output-dir",
            str(proof_dir),
        ], check=True)

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "convert_nlboot_manifest_to_sourceos_bootreleaseset.py"),
            "--manifest",
            str(ROOT / "contracts" / "sourceos" / "examples" / "nlboot-manifest.m2-demo.recovery.json"),
            "--token",
            str(ROOT / "contracts" / "sourceos" / "examples" / "nlboot-token.m2-demo.recovery.json"),
            "--output",
            str(generated_boot_release),
        ], check=True)

        # Synthetic equivalent of nlboot-plan output; this stays side-effect-free.
        boot_plan.write_text(json.dumps({
            "ok": True,
            "plan": {
                "action": "boot-recovery",
                "manifest_id": "urn:srcos:boot-manifest:m2-demo-recovery",
                "boot_release_set_id": "sbrs-nlboot-m2-demo-recovery-0001",
                "release_set_ref": "srset-m2-demo-0001",
                "artifacts": {
                    "kernel_ref": "urn:srcos:artifact:m2-demo-kernel",
                    "initrd_ref": "urn:srcos:artifact:m2-demo-initrd",
                    "rootfs_ref": "urn:srcos:artifact:m2-demo-rootfs"
                },
                "authorized_by": "urn:srcos:enrollment-token:m2-demo-recovery",
                "signature_algorithm": "rsa-pss-sha256",
                "crypto_profile": "fips-140-3-compatible",
                "execute": False
            }
        }, indent=2) + "\n", encoding="utf-8")

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "emit_sourceos_synthetic_boot_fingerprint.py"),
            "--release-set",
            str(proof_dir / "release-set.json"),
            "--boot-release-set",
            str(generated_boot_release),
            "--boot-plan",
            str(boot_plan),
            "--output",
            str(fingerprint),
        ], check=True)

        document = load(fingerprint)
        if document.get("kind") != "SourceOSFingerprint":
            raise SystemExit("ERR: synthetic boot output is not a SourceOSFingerprint")
        if document.get("subject", {}).get("subject_kind") != "boot_environment":
            raise SystemExit("ERR: synthetic boot fingerprint subject is not boot_environment")
        if document.get("runtime", {}).get("isolation") != "boot_env":
            raise SystemExit("ERR: synthetic boot fingerprint runtime isolation is not boot_env")
        if document.get("system", {}).get("boot_mode") != "recovery":
            raise SystemExit("ERR: synthetic boot fingerprint boot_mode is not recovery")
        if document.get("policy", {}).get("release_set_ref") != "srset-m2-demo-0001":
            raise SystemExit("ERR: synthetic boot fingerprint release_set_ref mismatch")
        if document.get("policy", {}).get("boot_release_set_ref") != "sbrs-nlboot-m2-demo-recovery-0001":
            raise SystemExit("ERR: synthetic boot fingerprint boot_release_set_ref mismatch")
        if document.get("compliance", {}).get("status") != "compliant":
            raise SystemExit("ERR: synthetic boot fingerprint did not report compliant")

    print("SourceOS synthetic boot fingerprint smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
