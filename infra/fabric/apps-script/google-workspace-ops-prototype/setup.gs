/**
 * Google Workspace Operations Prototype setup.
 *
 * Creates or validates the ledger tabs required by the
 * Google Workspace Operations Prototype v0 standard.
 */

const REQUIRED_TABS = {
  Workstreams: ['workstream_id', 'title', 'status', 'owner_group_id', 'canonical_issue_ref', 'primary_calendar_id', 'primary_drive_folder_ref', 'dashboard_key', 'created_at', 'updated_at'],
  Calendars: ['calendar_id', 'calendar_name', 'purpose', 'owning_group_id', 'visibility', 'default_event_metadata_profile', 'migration_target'],
  Groups: ['group_id', 'display_email', 'display_name', 'purpose', 'authority_level', 'mapped_roles', 'allowed_resources', 'owner', 'review_cadence'],
  Meetings: ['meeting_id', 'calendar_event_id', 'calendar_id', 'workstream_id', 'meeting_type', 'scheduled_start', 'scheduled_end', 'actual_status', 'attendee_groups', 'decisions_count', 'action_items_count', 'risks_count', 'source_note_ref', 'next_review_date'],
  Decisions: ['decision_id', 'workstream_id', 'source_meeting_id', 'title', 'decision_status', 'decision_text', 'alternatives_considered', 'owner_group_id', 'effective_at', 'review_at', 'artifact_refs'],
  Requests: ['request_id', 'request_type', 'requester_group_id', 'objective', 'expected_outcome', 'compensation_model', 'schedule_expectations', 'response_deadline', 'evaluation_criteria', 'status'],
  Responses: ['response_id', 'request_id', 'responder_ref', 'approach', 'terms', 'evidence_refs', 'questions', 'availability', 'proposed_pricing', 'status'],
  ActionItems: ['action_item_id', 'workstream_id', 'source_meeting_id', 'owner_ref', 'owner_group_id', 'title', 'due_date', 'status', 'blocker_flag', 'evidence_refs'],
  Risks: ['risk_id', 'workstream_id', 'severity', 'likelihood', 'impact', 'description', 'mitigation', 'owner_group_id', 'escalation_surface', 'status'],
  Artifacts: ['artifact_id', 'title', 'artifact_type', 'source_system', 'source_ref', 'canonicality', 'owning_workstream_id', 'owning_group_id', 'migration_target'],
  Automations: ['run_id', 'automation_name', 'trigger_type', 'source_object', 'target_object', 'started_at', 'completed_at', 'status', 'error', 'affected_records', 'replay_ref'],
  Dashboards: ['dashboard_key', 'panel_key', 'title', 'source_tab', 'metric_definition', 'refresh_cadence', 'owner_group_id', 'migration_target'],
  CloudVendorReadiness: ['cloud_vendor', 'gate_id', 'gate_group', 'status', 'blocking_flag', 'evidence_ref', 'owner_group_id', 'last_reviewed_at'],
  MigrationReadiness: ['prototype_object_type', 'prototype_surface', 'native_target_object', 'schema_stability', 'automation_stability', 'dashboard_regeneration_possible', 'migration_status', 'notes']
};

function setupOperationsLedger(spreadsheetId) {
  const ss = SpreadsheetApp.openById(spreadsheetId);
  Object.keys(REQUIRED_TABS).forEach(function(tabName) {
    const headers = REQUIRED_TABS[tabName];
    let sheet = ss.getSheetByName(tabName);
    if (!sheet) {
      sheet = ss.insertSheet(tabName);
    }
    const currentHeaders = sheet.getRange(1, 1, 1, Math.max(headers.length, sheet.getLastColumn() || 1)).getValues()[0];
    const hasHeaders = headers.every(function(header, index) {
      return currentHeaders[index] === header;
    });
    if (!hasHeaders) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.setFrozenRows(1);
    }
  });
}
