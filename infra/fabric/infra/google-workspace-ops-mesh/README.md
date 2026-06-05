# Google Workspace Operations Mesh — OpenTofu/Terraform Scaffold

Issue: #50
Related prototype: #49
Standards: SocioProphet/socioprophet-standards-storage#92
IaC decision: `IAC_DECISION.md`

## Purpose

This infrastructure-as-code root prepares the Google Workspace Operations Prototype for repeatable deployment when the team is ready.

It is apply-safe by default. The default configuration does not create groups, enable APIs, deploy Apps Script, create calendars, create Sheets, or build dashboards.

## IaC default

This mesh is **OpenTofu-first** while keeping Terraform-compatible HCL where practical.

The repository root `Makefile` uses:

```make
IAC ?= tofu
```

Use Terraform only as an explicit compatibility override:

```bash
make IAC=terraform terraform-workspace-mesh-plan
```

## Mesh components

| Plane | IaC role | Default |
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

## Quick commands from repository root

```bash
make validate-workspace-all
make terraform-workspace-mesh-init
make terraform-workspace-mesh-fmt
make terraform-workspace-mesh-validate
make terraform-workspace-mesh-plan
```

The target names retain `terraform-*` for operator familiarity, but run OpenTofu by default through `IAC ?= tofu`.

Equivalent direct commands:

```bash
cd infra/google-workspace-ops-mesh
tofu init
tofu fmt -check
tofu validate
tofu plan
```

With default variables, plan should only propose local generated files.

## Gated apply flags

| Variable | Default | Effect |
|---|---:|---|
| `enable_google_project_services` | `false` | Enables listed Google Cloud APIs in `google_project_id` |
| `enable_workspace_groups` | `false` | Creates Google Workspace groups from `workspace_groups` |
| `generate_local_deployment_files` | `true` | Writes local generated config artifacts |

## Generated files

When `generate_local_deployment_files = true`, the mesh writes files under:

```text
generated/google-workspace-ops-mesh/
```

Generated files are intended for local operator review and should not contain secrets.

## Deployment boundary

This IaC root does not run `clasp push`, enable scheduled Apps Script triggers, create live calendar events, or mutate the prototype ledger. Those actions remain gated by the handoff runbook and install checklist.

## Promotion path

1. `make validate-workspace-all`
2. `make terraform-workspace-mesh-init`
3. `make terraform-workspace-mesh-validate`
4. `make terraform-workspace-mesh-plan` with defaults
5. Fill real IDs in a local `terraform.tfvars`
6. Generate deployment configs
7. Run Apps Script parser tests and dry-run sync
8. Only then consider enabling API or group-management flags
