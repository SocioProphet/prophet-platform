#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        manifest = tmpdir / "manifest.json"
        receipt = tmpdir / "receipt.json"
        event = tmpdir / "manifest.validated.event.json"
        readout = tmpdir / "readout.json"

        manifest.write_text(
            json.dumps(
                {
                    "manifest_id": "manifest://liberty-stack/demo/0001",
                    "owner_ref": "actor://demo/operator",
                    "datasets": [
                        {
                            "dataset_id": "dataset://demo/docs",
                            "provider": "demo",
                            "service": "files",
                            "target_format": "portable_bundle",
                            "verification_method": "count_hash_metadata_review",
                        }
                    ],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        run("tools/validate_liberty_stack_manifest.py", "--manifest", str(manifest))
        run(
            "tools/emit_liberty_stack_receipt.py",
            "--action",
            "validate_manifest",
            "--subject-ref",
            "manifest://liberty-stack/demo/0001",
            "--status",
            "succeeded",
            "--output",
            str(receipt),
        )
        run(
            "tools/emit_manifest_validated_event.py",
            "--manifest-id",
            "manifest://liberty-stack/demo/0001",
            "--status",
            "pass",
            "--receipt-ref",
            str(receipt),
            "--output",
            str(event),
        )

        rendered = subprocess.check_output(
            [
                sys.executable,
                "tools/render_liberty_stack_readout.py",
                "--receipt",
                str(receipt),
                "--event",
                str(event),
            ],
            cwd=ROOT,
            text=True,
        )
        readout.write_text(rendered, encoding="utf-8")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
