# Deployment Runbook — Google Workspace Operations Prototype

Implementation issue: #49
Standards issue: SocioProphet/socioprophet-standards-storage#92

## Goal

Install the prototype into Google Apps Script without making Google Workspace the canonical system of record.

## Step 1 — Create the prototype ledger

1. Create a Google Sheet named `SocioProphet Operations Control Plane - Prototype`.
2. Open **Extensions → Apps Script**.
3. Copy these files into the Apps Script project:
   - `setup.gs`
   - `sync-calendar-events-to-meetings.gs`
   - `parser-test.gs`
   - `seed-dashboard-rows.gs`
4. Run `setupOperationsLedger('<spreadsheet-id>')` once.
5. Verify the required tabs and headers exist.

## Step 2 — Configure dry-run sync

1. Copy `config.example.json` into Apps Script project properties or a local config function.
2. Set `spreadsheetId` to the prototype ledger Sheet ID.
3. Set each calendar ID manually; do not create calendars automatically in this phase.
4. Keep `dryRun` set to `true`.
5. Run `runMetadataParserFixtureTest()`.
6. Run `runMetadataParserNegativeTest()`.
7. Run `seedDashboardRows('<spreadsheet-id>')`.
8. Run `syncCalendarEventsToMeetings(config)`.
9. Inspect `Automations` for succeeded, failed, or quarantined runs.

## Step 3 — Controlled mutation

Only after dry-run behavior is correct:

1. Set `dryRun` to `false`.
2. Add one test event to `SP - Cloud Vendor Strategy` with a valid `socioprophet:` metadata block.
3. Run `syncCalendarEventsToMeetings(config)`.
4. Verify exactly one `Meetings` row is upserted.
5. Verify one `Automations` row records the run.
6. Modify the same calendar event and rerun sync.
7. Confirm the same `meeting_id` is updated rather than duplicated.

## Required safety checks

- No secrets in event descriptions.
- No access tokens in Sheet rows.
- No sensitive personal identifiers in dashboard rows.
- Missing metadata must produce a quarantined automation run.
- Failed automation must write an error record if the `Automations` tab is reachable.
- Dashboard panels must remain projections over Sheet tabs.

## Rollback

1. Disable time-driven triggers.
2. Restore `dryRun` to `true`.
3. Copy affected `Meetings` and `Automations` rows into an incident/replay note.
4. Delete only prototype rows whose `run_id` or `meeting_id` matches the bad run.
5. Record the rollback in `Automations` with status `replayed` or `quarantined`.

## Promotion gate

This prototype is ready for SocioProphet-native migration when:

- calendar metadata survives two review cycles,
- meeting rows are stable,
- automation runs are replayable,
- dashboard seed rows produce useful management views,
- and all required objects have explicit migration targets.
