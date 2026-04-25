#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()


def refresh_manifest(path: Path, check: bool) -> bool:
    data = json.loads(path.read_text(encoding='utf-8'))
    bundle_path = Path(data['bundle'])
    rulepack_path = Path(data['rulepack'])

    expected_bundle = sha256_file(bundle_path)
    expected_rulepack = sha256_file(rulepack_path)

    changed = False
    if data.get('bundle_digest') != expected_bundle:
        data['bundle_digest'] = expected_bundle
        changed = True
    if data.get('rulepack_digest') != expected_rulepack:
        data['rulepack_digest'] = expected_rulepack
        changed = True

    if check:
        return not changed

    if changed:
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description='Refresh Fog Stack manifest bundle/rulepack digests')
    parser.add_argument('manifests', nargs='+', type=Path)
    parser.add_argument('--check', action='store_true', help='Fail if any manifest digest is stale')
    args = parser.parse_args()

    ok = True
    for manifest in args.manifests:
        ok = refresh_manifest(manifest, check=args.check) and ok

    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
