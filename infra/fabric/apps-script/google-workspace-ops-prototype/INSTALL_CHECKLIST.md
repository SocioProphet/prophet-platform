# Install Checklist — Google Workspace Operations Prototype

Implementation issue: #49
Standards issue: SocioProphet/socioprophet-standards-storage#92

Use this checklist before enabling any time-driven trigger or live write path.

## A. Repository state

- [ ] Confirm these files exist in the implementation repo:
  - [ ] `README.md`
  - [ ] `DEPLOYMENT.md`
  - [ ] `config.example.json`
  - [ ] `setup.gs`
  - [ ] `sync-calendar-events-to-meetings.gs`
  - [ ] `parser-test.gs`
  - [ ] `seed-dashboard-rows.gs`
  - [ ] `seed-workspace-rows.gs`
  - [ ] `fixtures/calendar-event.sample.json`
  - [ ] `fixtures/dashboard-seed-rows.v0.csv`
  - [ ] `fixtures/workspace-seed-rows.v0.json`

## B. Google Sheet setup

- [ ] Create Google Sheet named `SocioProphet Operations Control Plane - Prototype`.
- [ ] Record the Sheet ID in local config.
- [ ] Copy Apps Script files into a bound or standalone Apps Script project.
- [ ] Run `setupOperationsLedger('<spreadsheet-id>')`.
- [ ] Confirm all tabs exist:
  - [ ] Workstreams
  - [ ] Calendars
  - [ ] Groups
  - [ ] Meetings
  - [ ] Decisions
  - [ ] Requests
  - [ ] Responses
  - [ ] ActionItems
  - [ ] Risks
  - [ ] Artifacts
  - [ ] Automations
  - [ ] Dashboards
  - [ ] CloudVendorReadiness
  - [ ] MigrationReadiness

## C. Seed data

- [ ] Run `seedWorkspaceRows('<spreadsheet-id>')`.
- [ ] Run `seedDashboardRows('<spreadsheet-id>')`.
- [ ] Confirm `Workstreams` contains `cloud-vendor-strategy`.
- [ ] Confirm `Calendars` contains `SP - Cloud Vendor Strategy` and `SP - Launch Council` placeholder rows.
- [ ] Confirm `Groups` contains the first operating groups.
- [ ] Confirm `CloudVendorReadiness` contains AWS, Azure, and GCP gate rows.
- [ ] Confirm `MigrationReadiness` contains prototype object migration rows.

## D. Parser tests

- [ ] Run `runMetadataParserFixtureTest()`.
- [ ] Confirm result status is `passed`.
- [ ] Run `runMetadataParserNegativeTest()`.
- [ ] Confirm missing metadata fails closed.

## E. Dry-run sync

- [ ] Copy `config.example.json` into a local config function or project property.
- [ ] Set real `spreadsheetId`.
- [ ] Set real calendar IDs manually.
- [ ] Keep `dryRun: true`.
- [ ] Run `syncCalendarEventsToMeetings(config)`.
- [ ] Confirm an `Automations` row is written.
- [ ] Confirm missing metadata creates quarantined automation records.
- [ ] Confirm no `Meetings` rows are written during dry run.

## F. Controlled live write

- [ ] Create one test event in `SP - Cloud Vendor Strategy`.
- [ ] Include a valid `socioprophet:` metadata block.
- [ ] Set `dryRun: false`.
- [ ] Run `syncCalendarEventsToMeetings(config)`.
- [ ] Confirm exactly one `Meetings` row is created.
- [ ] Edit the same event and rerun sync.
- [ ] Confirm the same `meeting_id` is updated, not duplicated.

## G. Safety gates

- [ ] No secrets in event descriptions.
- [ ] No access tokens in Sheet rows.
- [ ] No sensitive personal identifiers in dashboard rows.
- [ ] No time-driven trigger is enabled until dry-run and controlled live write pass.
- [ ] Automation failure writes a failed or quarantined row when the `Automations` tab is reachable.
- [ ] Dashboard panels remain projections over ledger tabs.

## H. Promotion gate

- [ ] Two review cycles completed.
- [ ] Calendar metadata fields stable.
- [ ] Meeting rows stable.
- [ ] Dashboard seed rows useful.
- [ ] Automation runs replayable enough for diagnosis.
- [ ] Native SocioProphet migration targets explicit.
