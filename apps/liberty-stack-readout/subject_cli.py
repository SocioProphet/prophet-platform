from __future__ import annotations

import argparse
import json

from store import build_subject_readout


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Liberty Stack subject readout from local state")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--subject-ref", required=True)
    args = parser.parse_args()

    payload = build_subject_readout(args.state_root, args.subject_ref)
    if payload is None:
        print(json.dumps({"ok": False, "error": "subject not found"}))
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
