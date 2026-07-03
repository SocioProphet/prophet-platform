/**
 * Lightweight test harness for the Google Workspace Operations Prototype.
 *
 * Run `runMetadataParserFixtureTest()` from Apps Script after copying the
 * prototype files into a bound or standalone Apps Script project.
 */

function runMetadataParserFixtureTest() {
  const fixtureDescription = 'Weekly launch council.\n\n' +
    'socioprophet:\n' +
    '  workstream: cloud-vendor-strategy\n' +
    '  meeting_type: launch_council\n' +
    '  canonical_issue: SocioProphet/socioprophet-standards-storage#91\n' +
    '  decision_record: EDR-CVSP-2026-06-05-002\n' +
    '  dashboard_key: cloud_vendor_strategy\n' +
    '  owner_group: sp-launch-council\n' +
    '  attendee_groups:\n' +
    '    - sp-product\n' +
    '    - sp-engineering\n' +
    '    - sp-partner-gtm\n' +
    '  expected_outputs:\n' +
    '    - decisions\n' +
    '    - action_items\n' +
    '    - readiness_gate_updates\n' +
    '  migration_target: GovernanceSession\n';

  const metadata = parseSocioprophetMetadata_(fixtureDescription);
  assertEqual_('workstream', metadata.workstream, 'cloud-vendor-strategy');
  assertEqual_('meeting_type', metadata.meeting_type, 'launch_council');
  assertEqual_('canonical_issue', metadata.canonical_issue, 'SocioProphet/socioprophet-standards-storage#91');
  assertEqual_('dashboard_key', metadata.dashboard_key, 'cloud_vendor_strategy');
  assertArrayEqual_('attendee_groups', metadata.attendee_groups, ['sp-product', 'sp-engineering', 'sp-partner-gtm']);
  assertArrayEqual_('expected_outputs', metadata.expected_outputs, ['decisions', 'action_items', 'readiness_gate_updates']);

  const validation = validateMetadata_(metadata, ['workstream', 'meeting_type', 'canonical_issue', 'dashboard_key', 'expected_outputs']);
  assertEqual_('validation.ok', validation.ok, true);
  assertArrayEqual_('validation.missing', validation.missing, []);

  const fakeEvent = {
    getId: function() { return 'fixture-calendar-event-001'; },
    getStartTime: function() { return new Date('2026-06-12T15:00:00Z'); },
    getEndTime: function() { return new Date('2026-06-12T16:00:00Z'); }
  };
  const row = buildMeetingRow_(fakeEvent, {
    calendarId: 'TODO_SP_CLOUD_VENDOR_STRATEGY_CALENDAR_ID',
    workstreamDefault: 'cloud-vendor-strategy'
  }, metadata);

  assertEqual_('row.workstream_id', row.workstream_id, 'cloud-vendor-strategy');
  assertEqual_('row.meeting_type', row.meeting_type, 'launch_council');
  assertEqual_('row.actual_status', row.actual_status, 'scheduled');
  assertEqual_('row.attendee_groups', row.attendee_groups, 'sp-product,sp-engineering,sp-partner-gtm');

  return {
    status: 'passed',
    assertions: 11,
    fixture: 'calendar-event.sample.json'
  };
}

function runMetadataParserNegativeTest() {
  const metadata = parseSocioprophetMetadata_('No structured metadata here.');
  const validation = validateMetadata_(metadata, ['workstream', 'meeting_type', 'canonical_issue', 'dashboard_key', 'expected_outputs']);
  assertEqual_('validation.ok', validation.ok, false);
  assertArrayEqual_('validation.missing', validation.missing, ['workstream', 'meeting_type', 'canonical_issue', 'dashboard_key', 'expected_outputs']);
  return {
    status: 'passed',
    assertions: 2,
    fixture: 'missing-metadata'
  };
}

function assertEqual_(name, actual, expected) {
  if (actual !== expected) {
    throw new Error(name + ' expected=' + expected + ' actual=' + actual);
  }
}

function assertArrayEqual_(name, actual, expected) {
  if (!Array.isArray(actual)) {
    throw new Error(name + ' expected array actual=' + typeof actual);
  }
  if (actual.length !== expected.length) {
    throw new Error(name + ' expected length=' + expected.length + ' actual length=' + actual.length);
  }
  for (let i = 0; i < expected.length; i++) {
    if (actual[i] !== expected[i]) {
      throw new Error(name + '[' + i + '] expected=' + expected[i] + ' actual=' + actual[i]);
    }
  }
}
