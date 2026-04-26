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
    assert isinstance(data, dict)
    return data


def main() -> int:
    with TemporaryDirectory() as tmp:
        out = Path(tmp) / "proof"
        subprocess.run([
            sys.executable,
            str(ROOT / "tools" / "build_sourceos_m2_lifecycle_proof.py"),
            "--output-dir",
            str(out),
        ], check=True)

        expected = [
            "config-source.json",
            "release-set.json",
            "boot-release-set.json",
            "nlboot-crosswalk.json",
            "fingerprint.json",
            "compliance-result.json",
            "proof-index.json",
        ]
        for name in expected:
            if not (out / name).exists():
                raise SystemExit(f"ERR: missing generated proof artifact {name}")

        release_set = load(out / "release-set.json")
        boot_release_set = load(out / "boot-release-set.json")
        crosswalk = load(out / "nlboot-crosswalk.json")
        compliance = load(out / "compliance-result.json")

        if compliance.get("status") != "compliant":
            raise SystemExit("ERR: expected generated compliance result to be compliant")

        if crosswalk["release_set"]["sourceos_id"] != release_set["id"]:
            raise SystemExit("ERR: nlboot crosswalk release_set sourceos_id mismatch")
        if crosswalk["boot_release_set"]["sourceos_id"] != boot_release_set["id"]:
            raise SystemExit("ERR: nlboot crosswalk boot_release_set sourceos_id mismatch")
        if crosswalk["nlboot_manifest_id"] not in {artifact.get("uri") for artifact in boot_release_set.get("artifacts", [])}:
            raise SystemExit("ERR: BootReleaseSet artifacts do not include nlboot manifest id")

        proof_index = load(out / "proof-index.json")
        artifact_names = {item.get("path") for item in proof_index.get("artifacts", [])}
        for name in expected[:-1]:
            if name not in artifact_names:
                raise SystemExit(f"ERR: proof-index does not reference {name}")

    print("SourceOS M2 lifecycle proof smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
