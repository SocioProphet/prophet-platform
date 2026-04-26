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
        fingerprint = tmp_path / "synthetic-boot-fingerprint.json"
        compliance = tmp_path / "boot-fingerprint-compliance.json"
        boot_plan = ROOT / "contracts" / "sourceos" / "examples" / "nlboot-plan.m2-demo.recovery.json"

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

        if load(boot_plan).get("plan", {}).get("execute") is not False:
            raise SystemExit("ERR: captured nlboot-plan fixture must remain execute=false")

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

        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "check_sourceos_boot_fingerprint_compliance.py"),
            "--release-set",
            str(proof_dir / "release-set.json"),
            "--boot-release-set",
            str(generated_boot_release),
            "--fingerprint",
            str(fingerprint),
            "--output",
            str(compliance),
        ], check=True)

        document = load(fingerprint)
        if document.get("kind") != "SourceOSFingerprint":
            raise SystemExit("ERR: synthetic boot output is not a SourceOSFingerprint")
        result = load(compliance)
        if result.get("kind") != "SourceOSBootFingerprintComplianceResult":
            raise SystemExit("ERR: compliance output kind mismatch")
        if result.get("status") != "pass":
            raise SystemExit("ERR: boot fingerprint compliance did not pass")
        checks = {item.get("name"): item.get("status") for item in result.get("checks", [])}
        for required in ["release-set-ref", "boot-release-set-ref", "policy-bundle-ref", "runtime-isolation", "boot-mode"]:
            if checks.get(required) != "pass":
                raise SystemExit(f"ERR: compliance check did not pass: {required}")

    print("SourceOS synthetic boot fingerprint smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
