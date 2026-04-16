#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Liberty Stack workflow receipt")
    parser.add_argument("--action", required=True)
    parser.add_argument("--subject-ref", required=True)
    parser.add_argument("--status", required=True, choices=["succeeded", "failed", "blocked"])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    receipt = {
        "status": args.status,
        "action": args.action,
        "subject_ref": args.subject_ref,
    }

    text = json.dumps(receipt, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
