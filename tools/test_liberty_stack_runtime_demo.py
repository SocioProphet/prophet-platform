#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output = subprocess.check_output(
        [sys.executable, "tools/demo_liberty_stack_runtime.py"],
        cwd=ROOT,
        text=True,
    )
    payload = json.loads(output)
    assert payload["action"] == "validate_manifest"
    assert payload["status"] == "succeeded"
    assert payload["subject_ref"] == "manifest://liberty-stack/demo/0001"
    print(json.dumps({"ok": True, "subject_ref": payload["subject_ref"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
