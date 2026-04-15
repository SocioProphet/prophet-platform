#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover
    print('ERR: jsonschema is required for telemetry validation', file=sys.stderr)
    raise SystemExit(2) from exc

ROOT = Path(__file__).resolve().parents[1]
TELEMETRY = ROOT / 'telemetry'
SCHEMAS = TELEMETRY / 'schemas'
PLANES = TELEMETRY / 'planes'
CONTROLS = TELEMETRY / 'controls'
MANIFESTS = TELEMETRY / 'manifests'


def fail(msg: str) -> None:
    print(f'ERR: {msg}', file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'invalid JSON in {path.relative_to(ROOT)}: {exc}')


for required in [TELEMETRY, SCHEMAS, PLANES, CONTROLS, MANIFESTS]:
    if not required.exists():
        fail(f'missing required telemetry path: {required.relative_to(ROOT)}')

for schema_name in [
    'plane.schema.json',
    'control.schema.json',
    'event_manifest.schema.json',
    'policy_outcome.schema.json',
    'receipt.schema.json',
]:
    if not (SCHEMAS / schema_name).exists():
        fail(f'missing telemetry schema: telemetry/schemas/{schema_name}')

plane_schema = load_json(SCHEMAS / 'plane.schema.json')
control_schema = load_json(SCHEMAS / 'control.schema.json')
manifest_schema = load_json(SCHEMAS / 'event_manifest.schema.json')

plane_ids: set[str] = set()
for path in sorted(PLANES.glob('*.json')):
    data = load_json(path)
    try:
        jsonschema.validate(data, plane_schema)
    except jsonschema.ValidationError as exc:
        fail(f'plane schema validation failed for {path.relative_to(ROOT)}: {exc.message}')
    plane_id = data['plane_id']
    if plane_id in plane_ids:
        fail(f'duplicate plane_id: {plane_id}')
    plane_ids.add(plane_id)

for path in sorted(CONTROLS.glob('*.json')):
    data = load_json(path)
    try:
        jsonschema.validate(data, control_schema)
    except jsonschema.ValidationError as exc:
        fail(f'control schema validation failed for {path.relative_to(ROOT)}: {exc.message}')
    for control in data.get('controls', []):
        for plane_id in control.get('applies_to_planes', []):
            if plane_id not in plane_ids:
                fail(f'control {control["control_id"]} references unknown plane {plane_id}')

if not list(MANIFESTS.glob('*.json')):
    fail('telemetry/manifests is empty')

for path in sorted(MANIFESTS.glob('*.json')):
    data = load_json(path)
    try:
        jsonschema.validate(data, manifest_schema)
    except jsonschema.ValidationError as exc:
        fail(f'manifest schema validation failed for {path.relative_to(ROOT)}: {exc.message}')

    plane = data['plane']
    if plane not in plane_ids:
        fail(f'manifest {data["event"]} references unknown plane {plane}')

    owners = data.get('owners', [])
    if not owners:
        fail(f'manifest {data["event"]} has no owners')

    field_names = {field['name'] for field in data.get('fields', [])}
    forbidden = set(data.get('forbidden_fields', []))
    overlap = sorted(field_names & forbidden)
    if overlap:
        fail(f'manifest {data["event"]} has forbidden_fields also present in fields: {overlap}')

    retention_days = data.get('retention_days', 0)
    if retention_days <= 0:
        fail(f'manifest {data["event"]} has non-positive retention_days')

print('OK: telemetry package validation passed')
