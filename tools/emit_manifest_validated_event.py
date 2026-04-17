#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Liberty Stack manifest.validated event")
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--status", required=True, choices=["pass", "warn", "fail"])
    parser.add_argument("--receipt-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    event = {
        "event_id": f"event://liberty-stack/{args.manifest_id}/manifest-validated",
        "emitted_at": "2026-04-17T00:00:00Z",
        "manifest_id": args.manifest_id,
        "status": args.status,
        "receipt_ref": args.receipt_ref,
    }

    text = json.dumps(event, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
