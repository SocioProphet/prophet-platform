#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected object in {path}")
    return data


def main() -> int:
    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "boot-release-set.from-nlboot.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "convert_nlboot_manifest_to_sourceos_bootreleaseset.py"),
                "--manifest",
                str(ROOT / "contracts" / "sourceos" / "examples" / "nlboot-manifest.m2-demo.recovery.json"),
                "--token",
                str(ROOT / "contracts" / "sourceos" / "examples" / "nlboot-token.m2-demo.recovery.json"),
                "--output",
                str(output),
            ],
            check=True,
        )
        document = load_json(output)
        if document.get("kind") != "SourceOSBootReleaseSet":
            raise SystemExit("ERR: generated document is not a SourceOSBootReleaseSet")
        if "recovery" not in document.get("boot_modes", []):
            raise SystemExit("ERR: generated BootReleaseSet is missing recovery mode")
        if document.get("capabilities", {}).get("kexec") != "denied":
            raise SystemExit("ERR: adapter must not enable kexec")
        if document.get("capabilities", {}).get("network") != "restricted":
            raise SystemExit("ERR: adapter must keep network restricted")
        if document.get("authorization", {}).get("mode") != "single_use_code":
            raise SystemExit("ERR: expected single_use_code authorization")
        signature = (document.get("signatures") or [{}])[0]
        if signature.get("signature_ref") != "urn:srcos:signature:m2-demo-recovery":
            raise SystemExit("ERR: signature_ref was not preserved")

    print("nlboot to SourceOS BootReleaseSet adapter smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
