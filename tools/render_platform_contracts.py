#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    print('PyYAML is required to run this helper.', file=sys.stderr)
    raise

BASE = Path(__file__).resolve().parents[1]
CONTRACTS = BASE / 'contracts' / 'platform'

REQUIRED = [
    'service-catalog.yaml',
    'deployment-profiles.yaml',
    'hosting-boundaries.yaml',
    'fogstack-normalized-objects.yaml',
]


def load_yaml(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main() -> int:
    missing = [name for name in REQUIRED if not (CONTRACTS / name).exists()]
    if missing:
        print('Missing contract files:')
        for name in missing:
            print(f' - {name}')
        return 1

    loaded = {name: load_yaml(CONTRACTS / name) for name in REQUIRED}
    out_dir = BASE / 'generated' / 'reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / 'platform-contract-summary.txt'
    service_count = len(loaded['service-catalog.yaml'].get('services', []))
    profile_count = len(loaded['deployment-profiles.yaml'].get('profiles', []))
    object_families = list(loaded['fogstack-normalized-objects.yaml'].get('object_families', {}).keys())
    report.write_text(
        '\n'.join([
            'prophet-platform contract summary',
            f'services={service_count}',
            f'profiles={profile_count}',
            'object_families=' + ','.join(object_families),
        ]) + '\n',
        encoding='utf-8',
    )
    print(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
