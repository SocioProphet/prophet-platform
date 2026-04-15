#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOT_PREFIXES = [
    'Makefile',
    '.github/workflows/',
    'tools/',
    'contracts/platform/',
    'apps/',
    'infra/k8s/overlays/',
    'bundles/',
    'conformance/',
]


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()


def main() -> int:
    base_ref = os.environ.get('PREMERGE_BASE_REF', 'origin/main')
    head_ref = os.environ.get('PREMERGE_HEAD_REF', 'HEAD')

    diff_output = run(['git', 'diff', '--name-only', f'{base_ref}...{head_ref}'])
    changed = [line for line in diff_output.splitlines() if line.strip()]

    ahead_behind = run(['git', 'rev-list', '--left-right', '--count', f'{base_ref}...{head_ref}'])
    behind, ahead = [int(x) for x in ahead_behind.split()]

    hot_hits = [path for path in changed if any(path == prefix or path.startswith(prefix) for prefix in HOT_PREFIXES)]

    print('premerge audit summary')
    print(f'base_ref={base_ref}')
    print(f'head_ref={head_ref}')
    print(f'changed_files={len(changed)}')
    print(f'ahead={ahead}')
    print(f'behind={behind}')
    print(f'hot_path_hits={len(hot_hits)}')

    if hot_hits:
        print('hot paths:')
        for path in hot_hits:
            print(f' - {path}')

    if behind > 0:
        print('branch is behind base and should be refreshed before merge')
        return 1
    if not changed:
        print('no changed files detected; nothing to audit')
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
