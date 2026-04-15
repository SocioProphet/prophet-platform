#!/usr/bin/env python3
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / 'contracts' / 'forensic-genesis' / 'STANDARDS_PIN.yaml'
EXPECTED_REPO = 'SocioProphet/prophet-platform-standards'
REQUIRED_SCHEMA_SUFFIXES = [
    'edge.forensic.snmp.observed.v1.schema.json',
    'edge.forensic.mounts.observed.v1.schema.json',
    'edge.forensic.verify.completed.v1.schema.json',
    'edge.forensic.seal.completed.v1.schema.json',
]

def main() -> int:
    if not PIN_PATH.exists():
        print(f'missing pin file: {PIN_PATH.relative_to(ROOT)}')
        return 1
    data = yaml.safe_load(PIN_PATH.read_text())
    spec = data.get('spec', {})
    if spec.get('repo') != EXPECTED_REPO:
        print('unexpected standards repo in forensic genesis edge pin')
        return 1
    commit = spec.get('pin', {}).get('commit', '')
    if not isinstance(commit, str) or len(commit) != 40:
        print('invalid standards pin commit')
        return 1
    schemas = spec.get('consume', {}).get('schemas', [])
    for suffix in REQUIRED_SCHEMA_SUFFIXES:
        if not any(str(s).endswith(suffix) for s in schemas):
            print(f'missing schema pin reference: {suffix}')
            return 1
    print('forensic genesis edge standards pin validated')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
