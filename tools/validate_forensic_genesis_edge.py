#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / 'docs' / 'FORENSIC_GENESIS_EDGE_IMPORT.md',
    ROOT / 'docs' / 'LOCAL-FORENSIC-GENESIS-EDGE.md',
    ROOT / 'contracts' / 'forensic-genesis' / 'README.md',
    ROOT / 'infra' / 'local' / 'docker-compose.forensic-genesis-edge.yml',
    ROOT / '.github' / 'workflows' / 'validate-forensic-genesis-edge.yml',
]
TOPICS = [
    'edge.forensic.snmp.observed.v1',
    'edge.forensic.mounts.observed.v1',
    'edge.forensic.verify.completed.v1',
    'edge.forensic.seal.completed.v1',
]

def main() -> int:
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
    if missing:
        print('missing required forensic genesis edge files:')
        for m in missing:
            print(f' - {m}')
        return 1

    compose = (ROOT / 'infra' / 'local' / 'docker-compose.forensic-genesis-edge.yml').read_text()
    if 'redpanda:' not in compose or 'console:' not in compose:
        print('compose file missing expected services')
        return 1

    import_doc = (ROOT / 'docs' / 'FORENSIC_GENESIS_EDGE_IMPORT.md').read_text()
    local_doc = (ROOT / 'docs' / 'LOCAL-FORENSIC-GENESIS-EDGE.md').read_text()
    for topic in TOPICS:
        if topic not in import_doc or topic not in local_doc:
            print(f'missing topic reference: {topic}')
            return 1

    print('forensic genesis edge runtime surface validated')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
