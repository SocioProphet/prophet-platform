# Google Workspace Operations Mesh — Terraform Scaffold

Issue: #50
Related prototype: #49
Standards: SocioProphet/socioprophet-standards-storage#92

## Purpose

This Terraform root prepares the Google Workspace Operations Prototype for repeatable deployment when the team is ready.

It is apply-safe by default. The default configuration does not create groups, enable APIs, deploy Apps Script, create calendars, create Sheets, or build dashboards.

## Mesh components

| Plane | Terraform role | Default |
|---|---|---|
| Google Cloud project services | Optional enablement of APIs used by the prototype | disabled |
| Workspace groups | Optional creation of role groups through the Google Workspace provider | disabled |
| Apps Script / clasp | Generate local `.clasp.json` and prototype config files | enabled as local files only |
| Calendars | Track IDs and metadata for later bind | no calendar creation |
| Sheets ledger | Track ledger Sheet ID for generated config | no Sheet creation |
| Dashboard layer | Track dashboard seed contract | no dashboard creation |
| SocioProphet migration | Produce mesh summary outputs | local outputs only |

## Why this shape

Calendars, Sheets, Apps Script projects, and Looker Studio dashboards are treated as controlled deployment surfaces. This mesh records and generates configuration around them before attempting full automation.

## Quick commands

```bash
cd infra/google-workspace-ops-mesh
terraform init
terraform fmt -check
terraform validate
terraform plan
```

With default variables, `terraform plan` should only propose local generated files.

## Gated apply flags

| Variable | Default | Effect |
|---|---:|---|
| `enable_google_project_services` | `false` | Enables listed Google Cloud APIs in `google_project_id` |
| `enable_workspace_groups` | `false` | Creates Google Workspace groups from `workspace_groups` |
| `generate_local_deployment_files` | `true` | Writes local generated config artifacts |

## Generated files

When `generate_local_deployment_files = true`, Terraform writes files under:

```text
generated/google-workspace-ops-mesh/
```

Generated files are intended for local operator review and should not contain secrets.

## Deployment boundary

This Terraform root does not run `clasp push`, enable scheduled Apps Script triggers, create live calendar events, or mutate the prototype ledger. Those actions remain gated by the handoff runbook and install checklist.

## Promotion path

1. `terraform init`
2. `terraform validate`
3. `terraform plan` with defaults
4. Fill real IDs in a local `terraform.tfvars`
5. Generate deployment configs
6. Run Apps Script parser tests and dry-run sync
7. Only then consider enabling API or group-management flags
