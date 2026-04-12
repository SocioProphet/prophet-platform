# Platform contracts validation

## Current helper

`tools/render_platform_contracts.py` validates the presence of the current platform contract pack and emits a summary file under `generated/reports/`.

## Current contract files

- `contracts/platform/service-catalog.yaml`
- `contracts/platform/deployment-profiles.yaml`
- `contracts/platform/hosting-boundaries.yaml`
- `contracts/platform/fogstack-normalized-objects.yaml`

## Intended next step

Wire `tools/render_platform_contracts.py` into the repo validation path so platform contracts become part of normal validation rather than an optional helper.
