# Google Workspace Operations Prototype

Status: prototype scaffold
Implementation issue: #49
Standards issue: SocioProphet/socioprophet-standards-storage#92

## Purpose

This Apps Script scaffold prototypes the SocioProphet management control loop in Google Workspace before native SocioProphet migration.

The first executable loop is:

```text
Google Calendar event
  -> parse socioprophet metadata block
  -> upsert Meetings ledger row
  -> log AutomationRun
  -> support dashboard projections
  -> preserve migration-ready state
```

## Non-goals

- Do not create live calendars automatically.
- Do not manage Google Group memberships automatically.
- Do not treat Google Workspace as canonical truth.
- Do not store secrets or sensitive identifiers in event descriptions or logs.

## Files

- `config.example.json` — required configuration shape.
- `setup.gs` — creates or validates required sheet tabs.
- `sync-calendar-events-to-meetings.gs` — first sync loop.
- `fixtures/calendar-event.sample.json` — replay fixture for parser and upsert testing.

## Required Sheet tabs

- Workstreams
- Calendars
- Groups
- Meetings
- Decisions
- Requests
- Responses
- ActionItems
- Risks
- Artifacts
- Automations
- Dashboards
- CloudVendorReadiness
- MigrationReadiness

## Metadata block

Calendar event descriptions should include a YAML-like block:

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
  expected_outputs:
    - decisions
    - action_items
    - readiness_gate_updates
  migration_target: GovernanceSession
```

## Safety posture

The script fails closed when required metadata is missing. Failed runs are written to the `Automations` tab with status `failed` or `quarantined`; silent failures are prohibited.
