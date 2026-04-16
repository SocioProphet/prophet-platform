# Workflow Local Runner

This app provides the smallest boring execution seam for the current workbench and receipt stack.

It does **not** introduce a new workflow contract family.
Instead, it accepts workbench-side execution inputs, writes payload/event/receipt/catalog artifacts
into the existing `prophet-platform` state layout, and relies on the existing `evidence-receipts`
service to read those bundles back.

## Current scope

- health endpoint
- local execution endpoint
- writes payload, event, receipt, and catalog artifacts
- aligns receipt metadata to the workbench/run/receipt binding appendix in
  `socioprophet-standards-storage`

## Endpoints

- `GET /healthz`
- `POST /v1/runs/local-execute`

## Notes

This is a reference local path only.
Scheduler adapters, profiling artifacts, and deeper runtime law remain follow-on work.
