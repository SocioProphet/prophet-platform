/**
 * Seed first dashboard panel rows into the Dashboards ledger tab.
 */

const DASHBOARD_SEED_ROWS = [
  ['executive_control_plane', 'active_workstreams', 'Active workstreams by status', 'Workstreams', 'count_by(status)', 'daily', 'sp-exec-council', 'DashboardPanel'],
  ['executive_control_plane', 'open_blockers', 'Open blockers by severity', 'Risks', 'count_where(status=open AND severity in [high,sev1])', 'daily', 'sp-launch-council', 'DashboardPanel'],
  ['executive_control_plane', 'overdue_actions', 'Overdue action items', 'ActionItems', 'count_where(status!=closed AND due_date<today)', 'daily', 'sp-launch-council', 'DashboardPanel'],
  ['executive_control_plane', 'cloud_readiness', 'Cloud vendor readiness by cloud', 'CloudVendorReadiness', 'percent_complete_by(cloud_vendor)', 'daily', 'sp-launch-council', 'DashboardPanel'],
  ['cloud_vendor_strategy', 'aws_gates', 'AWS readiness gates', 'CloudVendorReadiness', 'gate_status_where(cloud_vendor=aws)', 'daily', 'sp-partner-gtm', 'DashboardPanel'],
  ['cloud_vendor_strategy', 'azure_gates', 'Azure readiness gates', 'CloudVendorReadiness', 'gate_status_where(cloud_vendor=azure)', 'daily', 'sp-partner-gtm', 'DashboardPanel'],
  ['cloud_vendor_strategy', 'gcp_gates', 'Google Cloud readiness gates', 'CloudVendorReadiness', 'gate_status_where(cloud_vendor=gcp)', 'daily', 'sp-partner-gtm', 'DashboardPanel'],
  ['cloud_vendor_strategy', 'conformance_coverage', 'Conformance fixture coverage', 'Artifacts', 'count_where(artifact_type=fixture AND owning_workstream_id=cloud-vendor-strategy)', 'daily', 'sp-engineering', 'DashboardPanel'],
  ['automation_health', 'automation_runs_by_status', 'Automation runs by status', 'Automations', 'count_by(status)', 'hourly', 'sp-agent-operators', 'DashboardPanel'],
  ['automation_health', 'failed_runs', 'Failed automation runs', 'Automations', 'count_where(status=failed)', 'hourly', 'sp-agent-operators', 'DashboardPanel'],
  ['automation_health', 'quarantined_runs', 'Quarantined automation runs', 'Automations', 'count_where(status=quarantined)', 'hourly', 'sp-agent-operators', 'DashboardPanel'],
  ['automation_health', 'last_successful_replay', 'Last successful replay per automation', 'Automations', 'max(completed_at) where status in [succeeded,replayed] group_by automation_name', 'hourly', 'sp-agent-operators', 'DashboardPanel'],
  ['migration_readiness', 'schema_stability', 'Prototype object schema stability', 'MigrationReadiness', 'count_by(schema_stability)', 'weekly', 'sp-engineering', 'DashboardPanel'],
  ['migration_readiness', 'automation_stability', 'Automation stability by object type', 'MigrationReadiness', 'count_by(automation_stability)', 'weekly', 'sp-agent-operators', 'DashboardPanel'],
  ['migration_readiness', 'manual_workflows_remaining', 'Manual workflows remaining', 'MigrationReadiness', 'count_where(migration_status=manual_only)', 'weekly', 'sp-product', 'DashboardPanel'],
  ['migration_readiness', 'native_targets', 'Native SocioProphet targets', 'MigrationReadiness', 'count_by(native_target_object)', 'weekly', 'sp-product', 'DashboardPanel']
];

function seedDashboardRows(spreadsheetId) {
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const sheet = ss.getSheetByName('Dashboards');
  if (!sheet) {
    throw new Error('Dashboards tab missing. Run setupOperationsLedger first.');
  }

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const dashboardKeyIndex = headers.indexOf('dashboard_key');
  const panelKeyIndex = headers.indexOf('panel_key');
  if (dashboardKeyIndex === -1 || panelKeyIndex === -1) {
    throw new Error('Dashboards tab missing dashboard_key or panel_key headers.');
  }

  const existing = {};
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    const values = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
    values.forEach(function(row, idx) {
      const key = row[dashboardKeyIndex] + ':' + row[panelKeyIndex];
      existing[key] = idx + 2;
    });
  }

  DASHBOARD_SEED_ROWS.forEach(function(seed) {
    const record = {
      dashboard_key: seed[0],
      panel_key: seed[1],
      title: seed[2],
      source_tab: seed[3],
      metric_definition: seed[4],
      refresh_cadence: seed[5],
      owner_group_id: seed[6],
      migration_target: seed[7]
    };
    const key = record.dashboard_key + ':' + record.panel_key;
    const targetRow = existing[key] || sheet.getLastRow() + 1;
    const rowValues = headers.map(function(header) {
      return record[header] !== undefined ? record[header] : '';
    });
    sheet.getRange(targetRow, 1, 1, headers.length).setValues([rowValues]);
  });

  return {
    status: 'seeded',
    rows: DASHBOARD_SEED_ROWS.length
  };
}
