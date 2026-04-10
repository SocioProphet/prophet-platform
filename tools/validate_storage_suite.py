#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ROOT / "tools" / "validate_storage_contracts.py",
    ROOT / "tools" / "validate_storage_vertical_slice.py",
    ROOT / "tools" / "validate_storage_receipts_vertical_slice.py",
    ROOT / "tools" / "validate_storage_live_typedb_mode.py",
]


def main() -> int:
    for check in CHECKS:
        proc = subprocess.run([sys.executable, str(check)], cwd=str(ROOT), check=False)
        if proc.returncode != 0:
            return proc.returncode
    print("OK: storage suite validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
