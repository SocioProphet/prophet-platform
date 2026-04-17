#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a thin Liberty Stack evidence readout")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--verification", type=Path, default=None)
    parser.add_argument("--event", type=Path, action="append", default=[])
    args = parser.parse_args()

    receipt = load_json(args.receipt)
    verification = load_json(args.verification) if args.verification else None
    events = [load_json(path) for path in args.event]

    readout = {
        "subject_ref": receipt.get("subject_ref"),
        "action": receipt.get("action"),
        "status": receipt.get("status"),
        "evidence_bundle_ref": receipt.get("evidence_bundle_ref"),
        "verification": verification,
        "events": events,
    }
    print(json.dumps(readout, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
