# Personal Intelligence Cell Live Lampstand Fixture

Status: live local-file fixture path
Related service: `apps/cell-service/`
Related Lampstand wrapper: `apps/lampstand/`
Related issue: `#384`

## Purpose

This fixture proves the real local-file path from Lampstand into the Personal Intelligence Cell runtime:

```text
local file -> apps/lampstand ingest_path -> carrier receipt/catalog/publication request -> CellService.ingest_lampstand_result -> Source + Signal + analytics
```

## Fixture file

```text
fixtures/cell/lampstand-live/local-carrier.md
```

The file contains deterministic text that can be ingested by Lampstand and then adapted into a cell signal.

## Runner

```text
tools/run_cell_lampstand_live_fixture.py
```

The runner:

1. imports the Lampstand wrapper from `apps/lampstand/src`;
2. ingests the fixture file with `prophet_platform_lampstand.ingest.ingest_path`;
3. creates a fixture cell, watch, and watch pattern;
4. calls `CellService.ingest_lampstand_result(...)`;
5. verifies evidence refs and carrier extraction;
6. prints a JSON summary.

## Operator command

```bash
PYTHONPATH=apps/cell-service/src:apps/lampstand/src \
python3 tools/run_cell_lampstand_live_fixture.py
```

This command writes Lampstand receipt/catalog/payload artifacts through the Lampstand wrapper. It is intentionally not run automatically by `validate_repo.py`.

## Validation

The non-mutating validator is:

```bash
python3 tools/validate_cell_lampstand_live_fixture.py
```

It verifies that:

- the fixture file exists and contains expected deterministic text;
- the live runner imports Lampstand and CellService;
- the runner uses `ingest_path` and `ingest_lampstand_result`;
- the runner expects evidence refs and analytics;
- the Lampstand wrapper exposes carrier ingestion, evidence receipt refs, and publication request output;
- the cell service and adapter expose the Lampstand seam.

`validate_repo.py` runs this validator, but not the mutating live runner.

## Why this matters

The earlier fixture used a static JSON result. This live fixture uses the actual Lampstand wrapper path, which means the adapter now has a route from real local files and generated receipts into the Personal Intelligence Cell signal/feed/publication loop.
