# IaC Decision — OpenTofu-first, Terraform-compatible

Issue: #50
Date: 2026-06-05

## Decision

Use OpenTofu as the default local infrastructure-as-code binary for the Google Workspace Operations Mesh.

Keep Terraform-compatible HCL and provider blocks where practical, but run Makefile mesh targets through `IAC ?= tofu` by default.

Operators may override with:

```bash
make IAC=terraform terraform-workspace-mesh-plan
```

## Rationale

Terraform was historically open source under MPL 2.0, but current Terraform releases are under HashiCorp's Business Source License model. OpenTofu is the community fork intended to preserve the open-source lineage and is maintained under the Linux Foundation ecosystem.

For SocioProphet, the correct default is therefore:

```text
new mesh work -> OpenTofu-first
legacy/customer compatibility -> Terraform override allowed
```

## Operational rule

Do not use Terraform-specific proprietary services or cloud-hosted state assumptions in this mesh unless explicitly documented.

The mesh should remain portable:

- local state by default,
- no mandatory Terraform Cloud dependency,
- no managed apply pipeline by default,
- no live Workspace mutation unless explicit gates are enabled,
- no provider credentials committed.

## Current Makefile behavior

The root `Makefile` uses:

```make
IAC ?= tofu
```

The target names retain `terraform-workspace-mesh-*` because that is common operator language and matches the first command set, but they run `tofu` unless overridden.

## Required local check

```bash
make validate-workspace-all
make terraform-workspace-mesh-init
make terraform-workspace-mesh-validate
make terraform-workspace-mesh-plan
```

If OpenTofu is not installed, install OpenTofu or run the same targets with `IAC=terraform` after reviewing licensing/compliance implications.
