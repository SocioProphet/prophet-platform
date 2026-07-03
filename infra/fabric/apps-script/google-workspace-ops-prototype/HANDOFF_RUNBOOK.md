# Handoff Runbook — Google Workspace Operations Prototype

Implementation issue: #49
Standards issue: SocioProphet/socioprophet-standards-storage#92
Companion strategy issue: SocioProphet/socioprophet-standards-storage#91

## 1. Purpose

This runbook hands the Google Workspace Operations Prototype from repository scaffold into controlled Workspace rehearsal.

The prototype exists to discover SocioProphet management semantics before native migration. Google Workspace is a projection and rehearsal surface. It is not the canonical system of record.

## 2. Lineage

```text
Cloud Vendor Strategy v1.1 standard
  -> Google Workspace Operations Prototype v0 standard
  -> Apps Script prototype scaffold
  -> repository validator and CI workflow
  -> manual Workspace installation
  -> dry-run sync
  -> controlled test write
  -> dashboard review
  -> migration-readiness review
  -> SocioProphet-native implementation
```

## 3. Source-of-truth boundaries

| Surface | Prototype role | Boundary |
|---|---|---|
| Google Calendar | Cadence and participation projection | Not the decision store |
| Google Groups | Role and access projection | Not durable identity truth |
| Google Drive | Prototype artifact store | Not the only standards store |
| Google Sheets | Temporary operating ledger | Not the final database |
| Looker Studio | Dashboard projection | Not source data |
| Apps Script | Automation rehearsal layer | Not final workflow engine |
| GitHub standards repos | Normative standards and contracts | Not runtime state database |
| SocioProphet future runtime | Native operating system | Final migration target |

## 4. Repository readiness gate

Before a Workspace installation, run:

```bash
python3 scripts/validate_google_workspace_ops_prototype.py
```

Expected output:

```text
PASS: Google Workspace Operations Prototype scaffold is valid
validated_root=apps-script/google-workspace-ops-prototype
required_files=13
required_tabs=14
apps_script_functions=6
```

If validation fails, use `CI_NOTES.md` before installation.

## 5. Installation sequence

### Step 1 — Create the ledger

1. Create a Google Sheet named `SocioProphet Operations Control Plane - Prototype`.
2. Record the Sheet ID in local configuration.
3. Open Apps Script from the Sheet or create a standalone Apps Script project.
4. Copy these `.gs` files into Apps Script:
   - `setup.gs`
   - `sync-calendar-events-to-meetings.gs`
   - `parser-test.gs`
   - `seed-dashboard-rows.gs`
   - `seed-workspace-rows.gs`
5. Run:

```javascript
setupOperationsLedger('<spreadsheet-id>')
```

### Step 2 — Seed prototype state

Run:

```javascript
seedWorkspaceRows('<spreadsheet-id>')
seedDashboardRows('<spreadsheet-id>')
```

Expected seeded tabs:

- `Workstreams`
- `Calendars`
- `Groups`
- `CloudVendorReadiness`
- `MigrationReadiness`
- `Dashboards`

### Step 3 — Replace placeholders

Replace placeholder IDs before operational use:

- `TODO_SP_CLOUD_VENDOR_STRATEGY_CALENDAR_ID`
- `TODO_SP_LAUNCH_COUNCIL_CALENDAR_ID`
- `TODO_GROUP_SP_EXEC_COUNCIL`
- `TODO_GROUP_SP_LAUNCH_COUNCIL`
- `TODO_GROUP_SP_PRODUCT`
- `TODO_GROUP_SP_ENGINEERING`
- `TODO_GROUP_SP_PARTNER_GTM`
- `TODO_GROUP_SP_AUDITORS`

Use stable group IDs where available, while keeping display email addresses as labels.

### Step 4 — Run parser tests

Run:

```javascript
runMetadataParserFixtureTest()
runMetadataParserNegativeTest()
```

Both should return `status: passed`.

### Step 5 — Dry-run sync

Use config derived from `config.example.json` with:

```json
{
  "dryRun": true
}
```

Run:

```javascript
syncCalendarEventsToMeetings(config)
```

Verify:

- `Automations` records the run.
- Invalid metadata creates quarantined records.
- `Meetings` is not changed during dry run.

### Step 6 — Controlled test write

Only after dry-run passes:

1. Create one test event on `SP - Cloud Vendor Strategy`.
2. Include a valid `socioprophet:` metadata block.
3. Set `dryRun: false`.
4. Run sync.
5. Confirm one `Meetings` row is created.
6. Modify the same event.
7. Rerun sync.
8. Confirm the same row is updated rather than duplicated.

## 6. Calendar event metadata template

```yaml
socioprophet:
  workstream: cloud-vendor-strategy
  meeting_type: launch_council
  canonical_issue: SocioProphet/socioprophet-standards-storage#91
  decision_record: EDR-CVSP-2026-06-05-002
  dashboard_key: cloud_vendor_strategy
  owner_group: sp-launch-council
  attendee_groups:
    - sp-product
    - sp-engineering
    - sp-partner-gtm
  expected_outputs:
    - decisions
    - action_items
    - readiness_gate_updates
  migration_target: GovernanceSession
```

Required fields:

- `workstream`
- `meeting_type`
- `canonical_issue`
- `dashboard_key`
- `expected_outputs`

## 7. First dashboard review

Use the seeded `Dashboards` tab to review four dashboards:

1. Executive Control Plane
2. Cloud Vendor Strategy
3. Automation Health
4. Migration Readiness

The dashboard review should answer:

- Which panels are useful immediately?
- Which panels cannot yet regenerate from ledger data?
- Which panels expose more detail than their audience needs?
- Which metrics should become SocioProphet-native `MetricDefinition` objects?

## 8. Two-cycle stabilization protocol

A prototype object is not migration-ready until it survives two review cycles.

Cycle review checklist:

- Calendar metadata fields remained stable.
- Meeting rows followed the ledger contract.
- Dashboard panels regenerated from ledger rows.
- Automation outcomes were visible in `Automations`.
- Placeholder IDs were resolved or explicitly deferred.
- Event descriptions and ledger rows stayed appropriate for their intended audience.

## 9. Migration-readiness gates

| Prototype object | Native target | Gate |
|---|---|---|
| Calendar metadata | `CadenceEvent`, `GovernanceSession` | Stable after two review cycles |
| Group rows | `RoleBinding`, `CapabilityGrant` | Real group IDs recorded |
| Meeting rows | `GovernanceSession` | Event upsert behavior confirmed |
| Automation rows | `AutomationRun`, `WorkflowExecution` | Failure and quarantine behavior proven |
| Dashboard rows | `DashboardPanel`, `MetricDefinition` | Panels regenerate from ledger data |
| Cloud readiness rows | `ReadinessGate` | Owner groups and evidence refs valid |

## 10. Live-trigger gate

Do not enable scheduled triggers until all are true:

- validator passes locally or in CI,
- Apps Script parser tests pass,
- seed rows are present,
- placeholders are reviewed,
- dry-run sync has executed,
- one controlled test write has succeeded,
- one update to the same event has proven idempotent upsert,
- rollback path is understood,
- `Automations` records success, failure, and quarantine cases.

## 11. Recovery procedure

If a live sync run behaves incorrectly:

1. Turn off scheduled triggers.
2. Return config to `dryRun: true`.
3. Identify affected rows by `run_id` and `meeting_id`.
4. Preserve a copy of affected prototype rows for review.
5. Remove only prototype rows created by the incorrect run.
6. Record recovery activity in `Automations`.
7. Resume live writes only after validator, parser tests, and dry run pass again.

## 12. Done definition

The prototype handoff is complete when:

- repository validator passes,
- CI workflow exists,
- install checklist exists,
- handoff runbook exists,
- ledger can be created,
- workspace and dashboard rows can be seeded,
- metadata parser tests pass,
- dry-run sync logs automation results,
- controlled test write creates one meeting row,
- idempotent update is proven,
- and migration readiness has at least one review cycle recorded.
