# CI Notes — Google Workspace Operations Prototype

Implementation issue: #49
Workflow: `.github/workflows/validate-google-workspace-ops-prototype.yml`
Validator: `scripts/validate_google_workspace_ops_prototype.py`

## Purpose

The CI workflow validates the repository scaffold before anyone copies the prototype into Google Apps Script or connects it to live Google Workspace resources.

This CI does **not** deploy the prototype. It only verifies that the repo-side contract is internally consistent.

## Local command

```bash
python3 scripts/validate_google_workspace_ops_prototype.py
```

## Expected success output

```text
PASS: Google Workspace Operations Prototype scaffold is valid
validated_root=apps-script/google-workspace-ops-prototype
required_files=13
required_tabs=14
apps_script_functions=6
```

## What the validator checks

| Check | Failure meaning | Remediation |
|---|---|---|
| Required files exist | Scaffold is incomplete. | Restore the missing file or update `fixture-contract.v0.json` only if the file was intentionally removed. |
| Apps Script functions exist | Apps Script install instructions reference a missing function. | Add the function or correct the contract and docs together. |
| `config.example.json` parses | Configuration cannot be copied safely. | Fix JSON syntax. |
| `dryRun` defaults to `true` | Prototype may mutate live sheets too early. | Set `dryRun` back to `true` in example config. |
| Required metadata fields exist | Calendar sync may not fail closed correctly. | Restore `workstream`, `meeting_type`, `canonical_issue`, `dashboard_key`, and `expected_outputs`. |
| `setup.gs` defines all tabs | Ledger creation will be incomplete. | Restore tab definitions in `REQUIRED_TABS`. |
| JSON fixtures parse | Replay / seed fixture is malformed. | Fix JSON syntax and rerun validator. |
| Dashboard CSV header matches contract | Dashboard seeding may write bad columns. | Restore expected CSV header. |
| Sync script contains safety markers | Fail-closed behavior may have been weakened. | Restore quarantine, metadata validation, dry-run, upsert, and automation logging paths. |

## Common failure examples

### Missing required file

```text
FAIL: missing required files: apps-script/google-workspace-ops-prototype/parser-test.gs
```

Meaning: a required artifact is missing from the scaffold. Restore the file or update the contract intentionally in the same change.

### Unsafe dry-run default

```text
FAIL: config.example.json must default dryRun to true
```

Meaning: the example configuration would permit mutation too early. Restore the safe default.

### Missing metadata field

```text
FAIL: requiredMetadataFields missing expected_outputs
```

Meaning: the calendar sync contract no longer validates one of the required structured metadata fields.

### Missing safety marker

```text
FAIL: sync script missing safety marker: quarantined
```

Meaning: the sync implementation may no longer quarantine invalid calendar events. Restore fail-closed behavior or intentionally update the validator after a design review.

## Design rule

Do not make the validator less strict to make CI green. If a rule is too strict, update the standard, fixture contract, validator, deployment docs, and issue thread together.

## Boundary

Passing CI means the repository scaffold is coherent. It does not mean:

- the Apps Script project has been deployed,
- Google Sheets permissions are correct,
- Calendar IDs are valid,
- Google Groups exist,
- Looker Studio dashboards are built,
- or time-driven triggers are safe to enable.

Those checks remain part of `INSTALL_CHECKLIST.md` and live Workspace deployment review.
