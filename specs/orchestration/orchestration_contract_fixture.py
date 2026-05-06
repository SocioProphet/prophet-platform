#!/usr/bin/env python3
'''
Canonical stdlib-only fixture for Sovereign Device Orchestration.

Run:
  python specs/orchestration/orchestration_contract_fixture.py
  python specs/orchestration/orchestration_contract_fixture.py --json
'''

from __future__ import annotations

import argparse
import json
import sys


REQUIRED = {
    'adapters': 'adapter_id',
    'device_nodes': 'node_id',
    'events': 'event_id',
    'routines': 'routine_id',
    'policy_decisions': 'decision_id',
    'receipts': 'receipt_id',
}

OUTCOMES = {'allowed', 'denied', 'requires_approval', 'requires_local_only', 'redacted', 'degraded'}
HIGH_RISK = {'high_risk_actuation', 'irreversible_action'}


def fixture_bundle() -> dict:
    return {
        'contract_version': 'sdo.v0.1',
        'bundle_id': 'bundle:fixture:home-assistant-demo:2026-05-05',
        'generated_at': '2026-05-05T18:45:00Z',
        'data_mode': 'fixture',
        'adapters': [
            {
                'adapter_id': 'adapter:home-assistant-fixture',
                'adapter_family': 'home_assistant',
                'operating_mode': 'fixture',
                'health': 'healthy',
                'credential_boundary': 'none',
                'capabilities': ['device_discovery', 'state_observation', 'routine_fixture_events'],
                'last_checked_at': '2026-05-05T18:45:00Z',
            },
            {
                'adapter_id': 'adapter:sourceos-local',
                'adapter_family': 'sourceos_shell',
                'operating_mode': 'local',
                'health': 'healthy',
                'credential_boundary': 'system_store',
                'capabilities': ['local_receipts', 'durable_queue', 'repair_replay'],
                'last_checked_at': '2026-05-05T18:45:00Z',
            },
            {
                'adapter_id': 'adapter:agentplane-fixture',
                'adapter_family': 'agentplane',
                'operating_mode': 'fixture',
                'health': 'healthy',
                'credential_boundary': 'none',
                'capabilities': ['agent_proposals', 'capability_checks'],
                'last_checked_at': '2026-05-05T18:45:00Z',
            },
            {
                'adapter_id': 'adapter:guardrail-fabric-fixture',
                'adapter_family': 'guardrail_fabric',
                'operating_mode': 'fixture',
                'health': 'healthy',
                'credential_boundary': 'none',
                'capabilities': ['policy_decisions', 'approval_requirements', 'redaction_requirements'],
                'last_checked_at': '2026-05-05T18:45:00Z',
            },
            {
                'adapter_id': 'adapter:google-home-placeholder',
                'adapter_family': 'google_home',
                'operating_mode': 'degraded',
                'health': 'degraded',
                'credential_boundary': 'external_connector',
                'capabilities': ['camera_history_search_planned', 'ask_home_planned'],
                'last_checked_at': '2026-05-05T18:45:00Z',
            },
        ],
        'device_nodes': [
            node('node:front-door-camera-01', 'Front Door Camera', 'camera', 'adapter:home-assistant-fixture', ['camera_event_summary', 'motion_detection', 'package_detection'], ['camera', 'privacy_sensitive', 'no_raw_video_default']),
            node('node:living-room-temp-01', 'Living Room Temperature Sensor', 'sensor', 'adapter:home-assistant-fixture', ['temperature_observation'], ['sensor', 'low_risk']),
            node('node:living-room-fan-01', 'Living Room Fan', 'appliance', 'adapter:home-assistant-fixture', ['power_toggle', 'fan_speed_set'], ['low_risk_actuation']),
            node('node:security-system-01', 'Household Security System', 'service', 'adapter:home-assistant-fixture', ['arm_alarm', 'disarm_alarm'], ['security', 'high_risk_actuation', 'approval_required']),
            node('node:agent-household-orchestrator', 'Household Orchestrator Agent', 'agent', 'adapter:agentplane-fixture', ['explain', 'search_receipts', 'propose_routine', 'draft_routine'], ['agent', 'no_direct_high_risk_actuation']),
        ],
        'routines': [
            {
                'routine_id': 'routine:cool-living-room-when-hot',
                'version': '0.1.0',
                'natural_language_description': 'When the living room temperature is above 76 F and someone is home, turn on the living room fan at medium speed.',
                'compiled_from': 'fixture',
                'triggers': [{'type': 'sensor_threshold', 'node_id': 'node:living-room-temp-01', 'metric': 'temperature_f', 'operator': '>', 'value': 76}],
                'preconditions': [{'type': 'occupancy', 'scope': 'home', 'state': 'present'}],
                'actions': [{'action_id': 'action:fan-medium', 'target_node_id': 'node:living-room-fan-01', 'action_type': 'set_fan_speed', 'capability_class': 'low_risk_actuation', 'parameters': {'speed': 'medium'}}],
                'allowed_node_ids': ['node:living-room-temp-01', 'node:living-room-fan-01'],
                'disallowed_node_ids': ['node:security-system-01', 'node:front-door-camera-01'],
                'safety_class': 'low_risk_actuation',
                'required_approval_mode': 'notify',
                'rollback_behavior': 'state_snapshot',
                'test_fixture_ids': ['event:sensor:living-room-temp-high'],
                'policy_package_refs': ['guardrail-fabric/device-orchestration@0.1'],
                'signature': 'fixture-signature:not-cryptographic',
                'revocation_status': 'active',
            },
            {
                'routine_id': 'routine:arm-security-after-midnight',
                'version': '0.1.0',
                'natural_language_description': 'After midnight, arm the household security system if no motion has been detected for 30 minutes.',
                'compiled_from': 'natural_language',
                'triggers': [{'type': 'time_window', 'after': '00:00', 'timezone': 'local'}],
                'preconditions': [{'type': 'motion_absent', 'duration_minutes': 30, 'scope': 'home'}],
                'actions': [{'action_id': 'action:arm-security', 'target_node_id': 'node:security-system-01', 'action_type': 'arm_alarm', 'capability_class': 'high_risk_actuation', 'parameters': {'mode': 'away'}}],
                'allowed_node_ids': ['node:security-system-01'],
                'disallowed_node_ids': ['node:front-door-camera-01'],
                'safety_class': 'high_risk_actuation',
                'required_approval_mode': 'explicit_user_approval',
                'rollback_behavior': 'manual_only',
                'test_fixture_ids': ['event:agent:propose-arm-security'],
                'policy_package_refs': ['guardrail-fabric/device-orchestration@0.1'],
                'signature': 'fixture-signature:not-cryptographic',
                'revocation_status': 'pending_review',
            },
        ],
        'events': [
            event('event:camera:package-delivered', 'camera_event', 'node:front-door-camera-01', 'node:front-door-camera-01', 'adapter:home-assistant-fixture', 0.83, {'summary': 'package delivered', 'clip_retained': False}, [], [], 'metadata_only'),
            event('event:sensor:living-room-temp-high', 'sensor_event', 'node:living-room-temp-01', 'node:living-room-temp-01', 'adapter:home-assistant-fixture', 0.99, {'temperature_f': 78.4}, ['routine:cool-living-room-when-hot'], [], 'none'),
            event('event:agent:propose-arm-security', 'agent_proposal', 'node:security-system-01', 'node:agent-household-orchestrator', 'adapter:agentplane-fixture', 0.72, {'proposed_action': 'arm_alarm'}, ['routine:arm-security-after-midnight'], ['decision:requires-approval-arm-security'], 'none'),
            event('event:agent:request-raw-camera-export', 'agent_proposal', 'node:front-door-camera-01', 'node:agent-household-orchestrator', 'adapter:agentplane-fixture', 0.64, {'requested_action': 'export_raw_video'}, [], ['decision:deny-raw-camera-export'], 'content_redacted'),
            event('event:adapter:google-home-degraded', 'adapter_degraded', 'node:front-door-camera-01', 'adapter:google-home-placeholder', 'adapter:google-home-placeholder', 1.0, {'status': 'disabled_in_fixture_mode'}, [], ['decision:degraded-google-home-placeholder'], 'none'),
        ],
        'policy_decisions': [
            decision('decision:allow-cool-living-room', 'allowed', 'node:living-room-fan-01', 'low_risk_actuation', 'routine:cool-living-room-when-hot', 'event:sensor:living-room-temp-high', ['Low-risk appliance actuation', 'Allowed target node']),
            decision('decision:requires-approval-arm-security', 'requires_approval', 'node:security-system-01', 'high_risk_actuation', 'routine:arm-security-after-midnight', 'event:agent:propose-arm-security', ['Security system actuation is high risk', 'Explicit user approval required']),
            decision('decision:deny-raw-camera-export', 'denied', 'node:front-door-camera-01', 'high_risk_actuation', None, 'event:agent:request-raw-camera-export', ['Raw camera export disabled by default', 'No raw video retention policy']),
            decision('decision:degraded-google-home-placeholder', 'degraded', 'node:front-door-camera-01', 'observe', None, 'event:adapter:google-home-degraded', ['External cloud connector unavailable in fixture mode']),
        ],
        'receipts': [
            receipt('receipt:event:package-delivered', 'event_observed', 'event:camera:package-delivered', None, None, 'node:front-door-camera-01', 'node:front-door-camera-01', 'adapter:home-assistant-fixture', 'observe', 'redacted', 0.83, []),
            receipt('receipt:event:living-room-temp-high', 'event_observed', 'event:sensor:living-room-temp-high', None, None, 'node:living-room-temp-01', 'node:living-room-temp-01', 'adapter:home-assistant-fixture', 'observe', 'allowed', 0.99, []),
            receipt('receipt:policy:allow-cool-living-room', 'policy_decision', 'event:sensor:living-room-temp-high', 'decision:allow-cool-living-room', 'routine:cool-living-room-when-hot', 'node:living-room-fan-01', 'adapter:guardrail-fabric-fixture', 'adapter:guardrail-fabric-fixture', 'low_risk_actuation', 'allowed', 1.0, ['receipt:event:living-room-temp-high']),
            receipt('receipt:agent:propose-arm-security', 'agent_proposal', 'event:agent:propose-arm-security', None, 'routine:arm-security-after-midnight', 'node:security-system-01', 'node:agent-household-orchestrator', 'adapter:agentplane-fixture', 'propose', 'requires_approval', 0.72, []),
            receipt('receipt:policy:requires-approval-arm-security', 'policy_decision', 'event:agent:propose-arm-security', 'decision:requires-approval-arm-security', 'routine:arm-security-after-midnight', 'node:security-system-01', 'adapter:guardrail-fabric-fixture', 'adapter:guardrail-fabric-fixture', 'high_risk_actuation', 'requires_approval', 1.0, ['receipt:agent:propose-arm-security']),
            receipt('receipt:policy:deny-raw-camera-export', 'policy_decision', 'event:agent:request-raw-camera-export', 'decision:deny-raw-camera-export', None, 'node:front-door-camera-01', 'adapter:guardrail-fabric-fixture', 'adapter:guardrail-fabric-fixture', 'high_risk_actuation', 'denied', 1.0, ['receipt:event:package-delivered']),
            receipt('receipt:adapter:google-home-degraded', 'event_observed', 'event:adapter:google-home-degraded', 'decision:degraded-google-home-placeholder', None, 'node:front-door-camera-01', 'adapter:google-home-placeholder', 'adapter:google-home-placeholder', 'observe', 'degraded', 1.0, []),
        ],
    }


def node(node_id: str, name: str, node_type: str, adapter: str, capabilities: list[str], labels: list[str]) -> dict:
    return {
        'node_id': node_id,
        'display_name': name,
        'node_type': node_type,
        'ecosystem_adapter': adapter,
        'owner_boundary': 'household' if node_type != 'agent' else 'personal',
        'location_scope': 'home' if node_type in {'camera', 'service'} else 'room' if node_type in {'sensor', 'appliance'} else 'none',
        'capabilities': capabilities,
        'attestation_state': 'fixture',
        'last_seen_at': '2026-05-05T18:45:00Z',
        'trust_state': 'limited' if 'high_risk_actuation' in labels or node_type == 'agent' else 'trusted',
        'policy_labels': labels,
        'revocation_status': 'active',
    }


def event(event_id: str, kind: str, subject: str, actor: str, adapter: str, confidence: float, state: dict, routines: list[str], decisions: list[str], redaction: str) -> dict:
    return {
        'event_id': event_id,
        'event_type': kind,
        'subject_node_id': subject,
        'actor_id': actor,
        'adapter_id': adapter,
        'occurred_at': '2026-05-05T18:05:00Z',
        'confidence': confidence,
        'observed_state_after': state,
        'related_routine_ids': routines,
        'related_policy_decision_ids': decisions,
        'evidence_links': [{'link_type': 'fixture', 'uri': 'fixture://' + event_id.replace(':', '/'), 'redaction_class': redaction}],
        'lineage_parent_ids': [],
        'privacy': {'retention_class': 'audit_30d', 'redaction_class': redaction, 'location_scope': 'home'},
    }


def decision(decision_id: str, outcome: str, subject: str, capability: str, routine_id: str | None, event_id: str, reasons: list[str]) -> dict:
    obj = {
        'decision_id': decision_id,
        'outcome': outcome,
        'evaluated_at': '2026-05-05T18:05:02Z',
        'actor_id': 'adapter:guardrail-fabric-fixture',
        'subject_node_id': subject,
        'event_id': event_id,
        'capability_class': capability,
        'policy_package': 'guardrail-fabric/device-orchestration@0.1',
        'reasons': reasons,
    }
    if routine_id:
        obj['routine_id'] = routine_id
    return obj


def receipt(receipt_id: str, kind: str, event_id: str, decision_id: str | None, routine_id: str | None, subject: str, actor: str, adapter: str, capability: str, outcome: str, confidence: float, parents: list[str]) -> dict:
    obj = {
        'receipt_id': receipt_id,
        'receipt_type': kind,
        'event_id': event_id,
        'subject_node_id': subject,
        'actor_id': actor,
        'source_adapter_id': adapter,
        'emitted_at': '2026-05-05T18:05:04Z',
        'capability_used': capability,
        'policy_outcome': outcome,
        'confidence': confidence,
        'evidence_links': [{'link_type': 'fixture', 'uri': 'fixture://' + receipt_id.replace(':', '/'), 'redaction_class': 'none'}],
        'lineage_parent_receipt_ids': parents,
        'retention_class': 'audit_1y',
        'redaction_class': 'content_redacted' if outcome == 'denied' else 'none',
        'signature': 'fixture-signature:not-cryptographic',
    }
    if decision_id:
        obj['policy_decision_id'] = decision_id
    if routine_id:
        obj['routine_id'] = routine_id
    return obj


def collect_ids(bundle: dict) -> tuple[dict[str, set[str]], list[str]]:
    errors = []
    ids = {}
    for group, field in REQUIRED.items():
        seen = set()
        for obj in bundle.get(group, []):
            value = obj.get(field)
            if not value:
                errors.append(group + ' object missing ' + field)
            elif value in seen:
                errors.append('duplicate ' + field + ': ' + value)
            seen.add(value)
        ids[group] = seen
    return ids, errors


def validate_bundle(bundle: dict) -> list[str]:
    ids, errors = collect_ids(bundle)
    adapter_ids = ids['adapters']
    node_ids = ids['device_nodes']
    event_ids = ids['events']
    routine_ids = ids['routines']
    decision_ids = ids['policy_decisions']
    receipt_ids = ids['receipts']

    for node_obj in bundle['device_nodes']:
        if node_obj['ecosystem_adapter'] not in adapter_ids:
            errors.append('unknown node adapter: ' + node_obj['node_id'])

    for event_obj in bundle['events']:
        if event_obj['subject_node_id'] not in node_ids:
            errors.append('unknown event subject: ' + event_obj['event_id'])
        if event_obj['actor_id'] not in node_ids and event_obj['actor_id'] not in adapter_ids:
            errors.append('unknown event actor: ' + event_obj['event_id'])
        if event_obj['adapter_id'] not in adapter_ids:
            errors.append('unknown event adapter: ' + event_obj['event_id'])
        for routine_id in event_obj.get('related_routine_ids', []):
            if routine_id not in routine_ids:
                errors.append('unknown related routine: ' + routine_id)
        for decision_id in event_obj.get('related_policy_decision_ids', []):
            if decision_id not in decision_ids:
                errors.append('unknown related decision: ' + decision_id)

    for routine_obj in bundle['routines']:
        if routine_obj['safety_class'] in HIGH_RISK and routine_obj['required_approval_mode'] not in {'explicit_user_approval', 'two_party_approval', 'admin_approval'}:
            errors.append('high-risk routine lacks explicit approval: ' + routine_obj['routine_id'])
        for action in routine_obj['actions']:
            if action['target_node_id'] not in node_ids:
                errors.append('unknown routine action target: ' + action['target_node_id'])

    for decision_obj in bundle['policy_decisions']:
        if decision_obj['outcome'] not in OUTCOMES:
            errors.append('invalid policy outcome: ' + decision_obj['decision_id'])
        if decision_obj['subject_node_id'] not in node_ids:
            errors.append('unknown decision subject: ' + decision_obj['decision_id'])
        if decision_obj['event_id'] not in event_ids:
            errors.append('unknown decision event: ' + decision_obj['decision_id'])

    for receipt_obj in bundle['receipts']:
        if receipt_obj['policy_outcome'] not in OUTCOMES:
            errors.append('invalid receipt outcome: ' + receipt_obj['receipt_id'])
        if receipt_obj['subject_node_id'] not in node_ids:
            errors.append('unknown receipt subject: ' + receipt_obj['receipt_id'])
        if receipt_obj['source_adapter_id'] not in adapter_ids:
            errors.append('unknown receipt adapter: ' + receipt_obj['receipt_id'])
        if receipt_obj['event_id'] not in event_ids:
            errors.append('unknown receipt event: ' + receipt_obj['receipt_id'])
        if receipt_obj.get('policy_decision_id') and receipt_obj['policy_decision_id'] not in decision_ids:
            errors.append('unknown receipt policy decision: ' + receipt_obj['receipt_id'])
        for parent in receipt_obj['lineage_parent_receipt_ids']:
            if parent not in receipt_ids:
                errors.append('unknown receipt parent: ' + parent)

    outcomes = {decision_obj['outcome'] for decision_obj in bundle['policy_decisions']}
    for required in {'allowed', 'denied', 'requires_approval', 'degraded'}:
        if required not in outcomes:
            errors.append('missing policy outcome fixture: ' + required)

    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    bundle = fixture_bundle()
    errors = validate_bundle(bundle)

    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0 if not errors else 1

    if errors:
        for error in errors:
            print('ERROR: ' + error, file=sys.stderr)
        return 1

    print('sovereign device orchestration fixture validation passed')
    print('adapters={} nodes={} events={} routines={} decisions={} receipts={}'.format(len(bundle['adapters']), len(bundle['device_nodes']), len(bundle['events']), len(bundle['routines']), len(bundle['policy_decisions']), len(bundle['receipts'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
