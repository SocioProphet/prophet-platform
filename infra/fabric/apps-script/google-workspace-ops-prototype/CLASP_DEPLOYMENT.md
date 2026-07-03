# clasp Deployment Notes — Google Workspace Operations Prototype

Implementation issue: #49

## Purpose

These notes describe how to push the prototype into an existing Apps Script project using `clasp`. This is an optional alternative to manual copy/paste from the Apps Script editor.

## Safety posture

The prototype is still a rehearsal layer. Keep `dryRun: true` until parser tests, seed rows, and dry-run sync have passed.

The manifest requests:

- Google Sheets access for the prototype ledger.
- Calendar read-only access for event sync.

It does not request Gmail, Drive, Groups, or Calendar write scopes.

## Files

- `appsscript.json` — Apps Script manifest.
- `.clasp.example.json` — example clasp config; copy to `.clasp.json` locally and replace the script ID.

## Local setup

From the repository root:

```bash
npm install -g @google/clasp
clasp login
cp apps-script/google-workspace-ops-prototype/.clasp.example.json .clasp.json
```

Edit `.clasp.json`:

```json
{
  "scriptId": "YOUR_APPS_SCRIPT_PROJECT_ID",
  "rootDir": "apps-script/google-workspace-ops-prototype"
}
```

Validate the repository scaffold first:

```bash
python3 scripts/validate_google_workspace_ops_prototype.py
```

Push to Apps Script:

```bash
clasp push
```

Open the Apps Script project:

```bash
clasp open
```

## First functions to run

In Apps Script, run these in order:

```javascript
setupOperationsLedger('<spreadsheet-id>')
seedWorkspaceRows('<spreadsheet-id>')
seedDashboardRows('<spreadsheet-id>')
runMetadataParserFixtureTest()
runMetadataParserNegativeTest()
```

Only after those pass should `syncCalendarEventsToMeetings(config)` be run against real calendars.

## Deployment boundary

A successful `clasp push` means files reached Apps Script. It does not prove:

- Sheet permissions are correct,
- calendar IDs are valid,
- group IDs are real,
- dry-run behavior has been reviewed,
- controlled test write has passed,
- or scheduled triggers are safe.

Those checks remain governed by `INSTALL_CHECKLIST.md` and `HANDOFF_RUNBOOK.md`.
