# Optional Workspace Groups Root

Issue: #50

## Purpose

This optional root manages Google Workspace groups only when we are ready to provide real Workspace provider configuration.

It is intentionally separate from the default `infra/google-workspace-ops-mesh` root because the Google Workspace provider requires `customer_id` during provider configuration. Keeping it separate allows the default mesh plan to remain local-file-only and provider-safe.

## Use only when ready

Do not run this root until:

- Workspace customer ID is known,
- Workspace admin impersonation policy is reviewed,
- credential handling is approved,
- group names and membership policy are approved,
- and group creation is explicitly authorized.

## Commands

```bash
cd infra/google-workspace-ops-mesh/optional-workspace-groups
tofu init
tofu validate
tofu plan
```

## Boundary

This optional root is not part of the default mesh plan. It exists for later controlled activation.
