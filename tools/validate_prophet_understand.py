#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'schemas/repo-intelligence/prophet-understanding.schema.json'
FIXTURE = ROOT / 'examples/repo-intelligence/prophet-understanding.fixture.json'
DOC = ROOT / 'docs/PROPHET_UNDERSTAND_REPO_INTELLIGENCE.md'
SCHEMA_ID = 'https://standards.socioprophet.org/schemas/repo-intelligence/prophet-understanding.schema.json'
SCHEMA_VERSION = 'prophet-understanding.v0'
NODE_KINDS = {'repo','directory','file','module','package','service','endpoint','schema','contract','document','workflow','test','config','runtime','policy','domain','concept','validator'}
EDGE_KINDS = {'contains','imports','depends_on','defines','documents','tests','configures','calls','owns','generates','validates','governed_by','impacted_by','related_to'}
POLICY_STATES = {'allow','warn','require_review','deny','unknown'}
DOC_MARKERS = ['Core artifact','Required top-level fields','Node taxonomy','Edge taxonomy','Source anchors','Provenance receipts','Guided tours','Diff impact sets','Policy states','Cross-repo responsibilities','v0 acceptance criteria','Non-goals']


def fail(msg: str) -> None:
    print(f'ERR: {msg}', file=sys.stderr)
    raise SystemExit(2)


def load(path: Path) -> Any:
    if not path.exists():
        fail(f'missing required file: {path.relative_to(ROOT)}')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        fail(f'invalid JSON in {path.relative_to(ROOT)}: {exc}')


def need(obj: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(keys - set(obj))
    if missing:
        fail(f'{where} missing keys: {", ".join(missing)}')


def as_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f'{where} must be an object')
    return value


def as_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f'{where} must be a list')
    return value


def enum(schema: dict[str, Any], def_name: str, prop: str) -> set[str]:
    try:
        values = schema['$defs'][def_name]['properties'][prop]['enum']
    except KeyError as exc:
        fail(f'schema missing enum $defs/{def_name}/properties/{prop}: {exc}')
    return set(values)


def stable_id(value: str, where: str) -> None:
    if not value or re.search(r'20\d{2}-\d{2}-\d{2}|T\d{2}:\d{2}:\d{2}|^/|^[A-Za-z]:\\|\\', value):
        fail(f'{where} has unstable id: {value!r}')


def relpath(path: str, where: str) -> None:
    if not path or path.startswith('/') or re.match(r'^[A-Za-z]:\\', path) or '..' in Path(path).parts:
        fail(f'{where} must be a repo-relative path: {path!r}')


def confidence(value: Any, where: str) -> None:
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        fail(f'{where} confidence must be numeric 0..1')


def anchor(value: Any, where: str) -> None:
    value = as_dict(value, where)
    need(value, {'path','start_line','end_line','content_hash'}, where)
    relpath(value['path'], f'{where}.path')
    if not isinstance(value['start_line'], int) or value['start_line'] < 1:
        fail(f'{where}.start_line must be >= 1')
    if not isinstance(value['end_line'], int) or value['end_line'] < value['start_line']:
        fail(f'{where}.end_line must be >= start_line')
    if not isinstance(value['content_hash'], str) or not value['content_hash'].startswith('sha256:'):
        fail(f'{where}.content_hash must start with sha256:')


def unique(items: list[dict[str, Any]], where: str) -> set[str]:
    seen: set[str] = set()
    for item in items:
        item_id = item.get('id')
        if not isinstance(item_id, str):
            fail(f'{where} item missing string id')
        stable_id(item_id, f'{where}.{item_id}')
        if item_id in seen:
            fail(f'duplicate {where} id: {item_id}')
        seen.add(item_id)
    return seen


def validate_schema(schema: dict[str, Any]) -> None:
    if schema.get('$id') != SCHEMA_ID:
        fail('schema $id drifted')
    if schema.get('properties', {}).get('schema_version', {}).get('const') != SCHEMA_VERSION:
        fail('schema_version const drifted')
    defs = as_dict(schema.get('$defs'), 'schema.$defs')
    for required in {'RepoMetadata','Generator','AgentIdentity','SourceAnchor','RepoNode','RepoEdge','Summary','GuidedTour','TourStep','DiffImpactSet','ProvenanceReceipt','ValidationResult','PolicyStatus','PolicyCheck'}:
        if required not in defs:
            fail(f'schema missing $defs/{required}')
    if not NODE_KINDS <= enum(schema, 'RepoNode', 'kind'):
        fail('schema RepoNode.kind enum is missing required values')
    if not EDGE_KINDS <= enum(schema, 'RepoEdge', 'kind'):
        fail('schema RepoEdge.kind enum is missing required values')
    if enum(schema, 'PolicyStatus', 'state') != POLICY_STATES:
        fail('schema PolicyStatus.state enum drifted')
    for name in ['RepoNode','RepoEdge','ProvenanceReceipt','DiffImpactSet','PolicyStatus']:
        definition = as_dict(defs[name], f'schema.$defs.{name}')
        if definition.get('additionalProperties') is not False:
            fail(f'schema.$defs.{name} must close additionalProperties')


def optional_jsonschema(schema: dict[str, Any], fixture: dict[str, Any]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        return
    try:
        jsonschema.Draft202012Validator(schema).validate(fixture)
    except Exception as exc:
        fail(f'fixture does not validate against JSON Schema: {exc}')


def validate_artifact(artifact: dict[str, Any]) -> None:
    need(artifact, {'schema_version','repo','generator','agent_identity','nodes','edges','summaries','tours','diff_impact_sets','provenance_receipts','validation_results','policy_status'}, 'artifact')
    if artifact['schema_version'] != SCHEMA_VERSION:
        fail('fixture schema_version drifted')

    repo = as_dict(artifact['repo'], 'artifact.repo')
    need(repo, {'full_name','default_branch','commit','generated_at','artifact_hash'}, 'artifact.repo')
    if not re.match(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$', repo['full_name']):
        fail('artifact.repo.full_name must be owner/name')
    if not re.match(r'^[0-9a-fA-F]{7,40}$', repo['commit']):
        fail('artifact.repo.commit must be SHA-like')
    if not repo['artifact_hash'].startswith('sha256:'):
        fail('artifact.repo.artifact_hash must start with sha256:')

    gen = as_dict(artifact['generator'], 'artifact.generator')
    need(gen, {'name','version','parser_versions'}, 'artifact.generator')
    as_dict(gen['parser_versions'], 'artifact.generator.parser_versions')
    need(as_dict(artifact['agent_identity'], 'artifact.agent_identity'), {'kind','id','did'}, 'artifact.agent_identity')

    receipts = [as_dict(x, 'receipt') for x in as_list(artifact['provenance_receipts'], 'provenance_receipts')]
    receipt_ids = unique(receipts, 'provenance_receipts')
    for receipt in receipts:
        where = f'receipt {receipt["id"]}'
        need(receipt, {'id','claim_type','generator','parser_version','input_source_hash','generated_at','confidence','validation_state','warnings'}, where)
        confidence(receipt['confidence'], where)
        if receipt['validation_state'] not in {'valid','warning','invalid','unknown'}:
            fail(f'{where} invalid validation_state')
        if not receipt['input_source_hash'].startswith('sha256:'):
            fail(f'{where}.input_source_hash must start with sha256:')

    nodes = [as_dict(x, 'node') for x in as_list(artifact['nodes'], 'nodes')]
    node_ids = unique(nodes, 'nodes')
    kinds: set[str] = set()
    for node in nodes:
        where = f'node {node["id"]}'
        need(node, {'id','kind','label','confidence','provenance_receipt_ids','metadata'}, where)
        if node['kind'] not in NODE_KINDS:
            fail(f'{where} has invalid kind')
        kinds.add(node['kind'])
        if 'path' in node:
            relpath(node['path'], f'{where}.path')
        if node['kind'] != 'repo':
            if 'source_anchor' not in node:
                fail(f'{where} missing source_anchor')
            anchor(node['source_anchor'], f'{where}.source_anchor')
        confidence(node['confidence'], where)
        missing = sorted(set(as_list(node['provenance_receipt_ids'], f'{where}.provenance_receipt_ids')) - receipt_ids)
        if missing:
            fail(f'{where} references unknown receipts: {", ".join(missing)}')
    for seed in {'repo','document','schema','contract','validator','policy','test'}:
        if seed not in kinds:
            fail(f'fixture missing seed node kind: {seed}')

    edges = [as_dict(x, 'edge') for x in as_list(artifact['edges'], 'edges')]
    edge_ids = unique(edges, 'edges')
    for edge in edges:
        where = f'edge {edge["id"]}'
        need(edge, {'id','kind','source','target','confidence','provenance_receipt_ids','metadata'}, where)
        if edge['kind'] not in EDGE_KINDS:
            fail(f'{where} has invalid kind')
        if edge['source'] not in node_ids or edge['target'] not in node_ids:
            fail(f'{where} has unknown endpoint')
        confidence(edge['confidence'], where)
        missing = sorted(set(as_list(edge['provenance_receipt_ids'], f'{where}.provenance_receipt_ids')) - receipt_ids)
        if missing:
            fail(f'{where} references unknown receipts: {", ".join(missing)}')

    for summary in [as_dict(x, 'summary') for x in as_list(artifact['summaries'], 'summaries')]:
        need(summary, {'id','node_id','text','confidence','provenance_receipt_ids'}, f'summary {summary.get("id")}')
        if summary['node_id'] not in node_ids:
            fail(f'summary {summary["id"]} references unknown node')
        confidence(summary['confidence'], f'summary {summary["id"]}')

    for tour in [as_dict(x, 'tour') for x in as_list(artifact['tours'], 'tours')]:
        need(tour, {'id','kind','title','steps','provenance_receipt_ids'}, f'tour {tour.get("id")}')
        order = 0
        for step in as_list(tour['steps'], f'tour {tour["id"]}.steps'):
            step = as_dict(step, f'tour {tour["id"]}.step')
            need(step, {'order','node_id','summary'}, f'tour {tour["id"]}.step')
            if step['order'] <= order:
                fail(f'tour {tour["id"]} step order must be increasing')
            order = step['order']
            if step['node_id'] not in node_ids:
                fail(f'tour {tour["id"]} references unknown node')
            for edge_id in step.get('edge_ids', []):
                if edge_id not in edge_ids:
                    fail(f'tour {tour["id"]} references unknown edge')

    valid_targets = node_ids | edge_ids | {'artifact:prophet-understanding.v0'}
    for diff in [as_dict(x, 'diff') for x in as_list(artifact['diff_impact_sets'], 'diff_impact_sets')]:
        need(diff, {'id','base','head','changed_paths','affected_nodes','affected_edges','affected_tests','affected_docs','affected_policies','risk','requires_review','provenance_receipt_ids'}, f'diff {diff.get("id")}')
        for path in as_list(diff['changed_paths'], f'diff {diff["id"]}.changed_paths'):
            relpath(path, f'diff {diff["id"]}.changed_path')
        for field in ['affected_nodes','affected_tests','affected_docs','affected_policies']:
            for node_id in as_list(diff[field], f'diff {diff["id"]}.{field}'):
                if node_id not in node_ids:
                    fail(f'diff {diff["id"]} references unknown {field}: {node_id}')
        for edge_id in as_list(diff['affected_edges'], f'diff {diff["id"]}.affected_edges'):
            if edge_id not in edge_ids:
                fail(f'diff {diff["id"]} references unknown edge: {edge_id}')

    for result in [as_dict(x, 'validation') for x in as_list(artifact['validation_results'], 'validation_results')]:
        need(result, {'id','check_id','target_id','status','severity','message'}, f'validation {result.get("id")}')
        if result['status'] not in {'pass','warn','fail','skip'}:
            fail(f'validation {result["id"]} invalid status')
        if result['target_id'] not in valid_targets:
            fail(f'validation {result["id"]} references unknown target')

    policy = as_dict(artifact['policy_status'], 'policy_status')
    need(policy, {'state','checks'}, 'policy_status')
    if policy['state'] not in POLICY_STATES:
        fail('policy_status.state invalid')
    for check in as_list(policy['checks'], 'policy_status.checks'):
        check = as_dict(check, 'policy_status.check')
        need(check, {'id','state','message','evidence_receipt_ids'}, f'policy check {check.get("id")}')
        if check['state'] not in POLICY_STATES:
            fail(f'policy check {check["id"]} invalid state')
        missing = sorted(set(as_list(check['evidence_receipt_ids'], f'policy check {check["id"]}.evidence_receipt_ids')) - receipt_ids)
        if missing:
            fail(f'policy check {check["id"]} references unknown receipts: {", ".join(missing)}')


def validate_doc() -> None:
    if not DOC.exists():
        fail(f'missing doc: {DOC.relative_to(ROOT)}')
    text = DOC.read_text(encoding='utf-8', errors='replace')
    for marker in DOC_MARKERS:
        if marker not in text:
            fail(f'doc missing marker: {marker}')


def main() -> None:
    schema = as_dict(load(SCHEMA), 'schema')
    fixture = as_dict(load(FIXTURE), 'fixture')
    validate_schema(schema)
    optional_jsonschema(schema, fixture)
    validate_artifact(fixture)
    validate_doc()
    print('OK: Prophet Understand repo intelligence validation passed')


if __name__ == '__main__':
    main()
