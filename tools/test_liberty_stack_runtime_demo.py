#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]

# The readout fields that make this a real check rather than a smoke test. These were bare
# `assert`s, which `python -O` strips: under -O the tool inspected nothing and still printed
# `{"ok": true}`. They are explicit raises now so the check survives optimisation.
EXPECTED_READOUT = {
    "action": "validate_manifest",
    "status": "succeeded",
    "subject_ref": "manifest://liberty-stack/demo/0001",
}


class DemoCheckFailure(RuntimeError):
    """The Liberty Stack runtime demo did not produce the expected readout."""


def iter_json_documents(text: str) -> Iterator[Any]:
    """Yield each top-level JSON document from a concatenated stream."""
    decoder = json.JSONDecoder()
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        document, index = decoder.raw_decode(text, index)
        yield document


def main() -> int:
    output = subprocess.check_output(
        [sys.executable, "tools/demo_liberty_stack_runtime.py"],
        cwd=ROOT,
        text=True,
    )

    # The demo prints two documents: a one-line summary from the manifest tool, then the
    # readout. Parsing the stream as a single object raised JSONDecodeError before the
    # checks below were ever reached, so this tool could not pass even in principle.
    documents = list(iter_json_documents(output))
    if not documents:
        raise DemoCheckFailure("demo produced no JSON output")
    payload = documents[-1]

    if not isinstance(payload, dict):
        raise DemoCheckFailure(f"readout is {type(payload).__name__}, expected a JSON object")

    for key, expected in EXPECTED_READOUT.items():
        actual = payload.get(key)
        if actual != expected:
            raise DemoCheckFailure(f"readout {key}: expected {expected!r}, got {actual!r}")

    print(json.dumps({"ok": True, "subject_ref": payload["subject_ref"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
