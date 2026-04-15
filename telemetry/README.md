# Transparent Telemetry Seed Package

This package is the runtime-facing seed for the transparent telemetry model.

It is intentionally small and exists to let `prophet-platform` start implementing one narrow slice without importing the entire normative standards corpus.

## Initial scope

The first runtime slice is:
- conversation streaming lifecycle
- citation and source UX summaries
- experiment exposure disclosure for that slice
- auditable citation resolution receipts
- live telemetry inspector support

## Package layout

- `telemetry/planes/` plane definitions by purpose
- `telemetry/controls/` user- and policy-facing controls
- `telemetry/schemas/` machine-readable schema contracts
- `telemetry/manifests/` event family manifests for the first slice

## Design constraints

1. Reliability telemetry must continue to function when analytics is disabled.
2. Product analytics must not carry raw prompt text, raw assistant text, file names, or content snippets for this slice.
3. Experiment exposure must be visible and non-essential by default.
4. Citation handling must emit auditable receipts without broad content leakage.
5. Every outbound decision should be reducible to an inspector-visible policy outcome.

## Why this lives in prophet-platform

`prophet-platform` is the runtime and deployment hub where platform contracts become running services. This package is therefore runtime-facing and belongs here.

The larger normative model can later be mirrored or formalized upstream in standards repositories, but the platform needs an implementable seed now.

## Immediate next work

1. Wire manifest loading and schema validation in CI.
2. Add a policy reducer that resolves event -> manifest -> action.
3. Write receipts to a local inspector-visible stream.
4. Instrument only the first reference slice before broadening coverage.
