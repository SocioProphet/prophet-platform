/**
 * Seed first workspace operating rows into the prototype ledger.
 *
 * This populates Workstreams, Calendars, Groups, CloudVendorReadiness,
 * and MigrationReadiness with starter rows for the cloud-vendor-strategy
 * workstream. TODO placeholders must be replaced before relying on access
 * or calendar IDs operationally.
 */

const WORKSPACE_SEED_ROWS = {
  Workstreams: [
    {
      workstream_id: 'cloud-vendor-strategy',
      title: 'Cloud Vendor Strategy v1.1',
      status: 'active',
      owner_group_id: 'sp-launch-council',
      canonical_issue_ref: 'SocioProphet/socioprophet-standards-storage#91',
      primary_calendar_id: 'TODO_SP_CLOUD_VENDOR_STRATEGY_CALENDAR_ID',
      primary_drive_folder_ref: '/Prophet Operations/03-Cloud-Vendor-Strategy/',
      dashboard_key: 'cloud_vendor_strategy',
      created_at: '2026-06-05T00:00:00Z',
      updated_at: '2026-06-05T00:00:00Z'
    }
  ],
  Calendars: [
    {
      calendar_id: 'TODO_SP_CLOUD_VENDOR_STRATEGY_CALENDAR_ID',
      calendar_name: 'SP - Cloud Vendor Strategy',
      purpose: 'AWS Azure GCP marketplace and cloud ISV execution cadence',
      owning_group_id: 'sp-launch-council',
      visibility: 'restricted',
      default_event_metadata_profile: 'calendar-event-metadata.v0',
      migration_target: 'CadenceSurface'
    },
    {
      calendar_id: 'TODO_SP_LAUNCH_COUNCIL_CALENDAR_ID',
      calendar_name: 'SP - Launch Council',
      purpose: 'Cross-functional launch governance and approval cadence',
      owning_group_id: 'sp-exec-council',
      visibility: 'restricted',
      default_event_metadata_profile: 'calendar-event-metadata.v0',
      migration_target: 'CadenceSurface'
    }
  ],
  Groups: [
    ['TODO_GROUP_SP_EXEC_COUNCIL', 'sp-exec-council@example.com', 'SP Executive Council', 'Executive sponsorship and escalation authority', 'steward', 'ExecutiveSponsor,EscalationAuthority', 'dashboard:executive_control_plane', 'sp-exec-council', 'monthly'],
    ['TODO_GROUP_SP_LAUNCH_COUNCIL', 'sp-launch-council@example.com', 'SP Launch Council', 'Cross-functional launch governance', 'approver', 'LaunchCouncilMember,MarketplaceReadinessReviewer', 'calendar:SP - Launch Council,calendar:SP - Cloud Vendor Strategy,dashboard:cloud_vendor_strategy', 'sp-exec-council', 'monthly'],
    ['TODO_GROUP_SP_PRODUCT', 'sp-product@example.com', 'SP Product', 'Packaging plan catalog and product decisions', 'reviewer', 'ProductOwner,PlanCatalogOwner', 'dashboard:cloud_vendor_strategy', 'sp-launch-council', 'monthly'],
    ['TODO_GROUP_SP_ENGINEERING', 'sp-engineering@example.com', 'SP Engineering', 'Spine adapters conformance and runtime implementation', 'contributor', 'EngineeringOwner,AdapterImplementer,ConformanceOwner', 'dashboard:automation_health,dashboard:migration_readiness', 'sp-launch-council', 'monthly'],
    ['TODO_GROUP_SP_PARTNER_GTM', 'sp-partner-gtm@example.com', 'SP Partner GTM', 'Cloud partner marketplace and co-sell motion', 'contributor', 'PartnerOwner,ListingOwner,GTMOwner', 'dashboard:cloud_vendor_strategy', 'sp-launch-council', 'monthly'],
    ['TODO_GROUP_SP_AUDITORS', 'sp-auditors@example.com', 'SP Auditors', 'Read-only governance visibility', 'observer', 'Auditor,EvidenceReviewer', 'dashboard:executive_control_plane,dashboard:cloud_vendor_strategy', 'sp-exec-council', 'monthly']
  ],
  CloudVendorReadiness: [
    ['aws', 'aws-plan-map', 'adapter_mapping', 'seeded', 'true', 'docs/standards/cloud-vendor-strategy/adapters/aws/offer-map.stub.yaml', 'sp-engineering', '2026-06-05T00:00:00Z'],
    ['azure', 'azure-plan-map', 'adapter_mapping', 'seeded', 'true', 'docs/standards/cloud-vendor-strategy/adapters/azure/offer-map.stub.yaml', 'sp-engineering', '2026-06-05T00:00:00Z'],
    ['gcp', 'gcp-plan-map', 'adapter_mapping', 'seeded', 'true', 'docs/standards/cloud-vendor-strategy/adapters/gcp/offer-map.stub.yaml', 'sp-engineering', '2026-06-05T00:00:00Z'],
    ['all', 'marketplace-readiness-kit', 'launch_readiness', 'seeded', 'true', 'docs/standards/cloud-vendor-strategy/marketplace-readiness-kit/gates.v1.md', 'sp-launch-council', '2026-06-05T00:00:00Z']
  ],
  MigrationReadiness: [
    ['calendar_event_metadata', 'Google Calendar description block', 'CadenceEvent,GovernanceSession', 'seeded', 'not_started', 'partial', 'prototype', 'Requires two review cycles before migration.'],
    ['group_binding', 'Google Groups / Cloud Identity', 'RoleBinding,CapabilityGrant', 'seeded', 'not_started', 'partial', 'prototype', 'Group IDs must replace TODO placeholders.'],
    ['automation_run', 'Apps Script Automations tab', 'AutomationRun,WorkflowExecution', 'seeded', 'fixture_only', 'yes', 'prototype', 'Replay refs needed for full migration readiness.'],
    ['dashboard_panel', 'Sheets / Looker Studio projection', 'DashboardPanel,MetricDefinition', 'seeded', 'not_started', 'yes', 'prototype', 'Panels must remain ledger-derived.']
  ]
};

function seedWorkspaceRows(spreadsheetId) {
  const ss = SpreadsheetApp.openById(spreadsheetId);
  let totalRows = 0;

  Object.keys(WORKSPACE_SEED_ROWS).forEach(function(tabName) {
    const sheet = ss.getSheetByName(tabName);
    if (!sheet) {
      throw new Error(tabName + ' tab missing. Run setupOperationsLedger first.');
    }
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const rows = WORKSPACE_SEED_ROWS[tabName];
    rows.forEach(function(row) {
      const rowObject = Array.isArray(row) ? arrayToObject_(headers, row) : row;
      const keyColumn = inferKeyColumn_(tabName);
      upsertByKey_(sheet, keyColumn, rowObject);
      totalRows += 1;
    });
  });

  return {
    status: 'seeded',
    rows: totalRows
  };
}

function inferKeyColumn_(tabName) {
  const map = {
    Workstreams: 'workstream_id',
    Calendars: 'calendar_id',
    Groups: 'group_id',
    CloudVendorReadiness: 'gate_id',
    MigrationReadiness: 'prototype_object_type'
  };
  if (!map[tabName]) {
    throw new Error('No key column mapping for ' + tabName);
  }
  return map[tabName];
}

function arrayToObject_(headers, row) {
  const out = {};
  headers.forEach(function(header, index) {
    out[header] = row[index] !== undefined ? row[index] : '';
  });
  return out;
}
