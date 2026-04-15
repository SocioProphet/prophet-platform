#!/usr/bin/env python3
"""Minimal validator for example payloads in the Next Gen TOM brokerage package."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'specs' / 'brokerage' / 'events' / 'examples'


def load(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    required = [
        EXAMPLES / 'service-request.example.json',
        EXAMPLES / 'service-instance.example.json',
        EXAMPLES / 'request.submitted.event.json',
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print('Missing example files:')
        for item in missing:
            print(f' - {item}')
        return 1
    for path in required:
        load(path)
    print('Example payloads parse successfully.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
