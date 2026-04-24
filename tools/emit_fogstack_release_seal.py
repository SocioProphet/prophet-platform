#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description='Emit a Fog Stack release seal from artifact files')
    parser.add_argument('--bundle-id', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--artifact', action='append', nargs=2, metavar=('LABEL', 'PATH'), required=True,
                        help='Artifact label and file path; may be repeated')
    parser.add_argument('--notes', default=None)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()

    artifact_hashes: list[dict[str, str]] = []
    for label, path_str in args.artifact:
        p = Path(path_str)
        artifact_hashes.append({
            'label': label,
            'ref': str(p),
            'hash': sha256_file(p),
        })

    artifact_hashes.sort(key=lambda x: x['label'])
    root_material = json.dumps(artifact_hashes, sort_keys=True).encode('utf-8')
    release_root_hash = 'sha256:' + hashlib.sha256(root_material).hexdigest()

    seal = {
        'kind': 'FogStackReleaseSeal',
        'schema_version': 'v0.1',
        'bundle_id': args.bundle_id,
        'version': args.version,
        'algorithm': 'sha256',
        'release_root_hash': release_root_hash,
        'artifact_hashes': artifact_hashes,
        'notes': args.notes,
    }

    text = json.dumps(seal, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
