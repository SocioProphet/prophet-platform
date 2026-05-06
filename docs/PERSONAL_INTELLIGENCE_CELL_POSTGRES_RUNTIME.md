# Personal Intelligence Cell Postgres Runtime

Status: first live-runtime hardening lane
Related service: `apps/cell-service/`
Related issue: `#384`

## Purpose

This document defines the first operational Postgres path for the Personal Intelligence Cell runtime. The service remains able to run in memory for tests and demos, but now has a concrete migration and live replay path for Postgres-backed control-plane state.

## Runtime pieces

- `apps/cell-service/src/cell_service/postgres_repository.py`
  - body-first repository implementation over Postgres tables.
  - generic `create`, `put`, `get`, `list`, and `exists` operations.

- `apps/cell-service/src/cell_service/postgres_migrations.py`
  - migration file discovery;
  - SHA-256 migration planning;
  - `cell_schema_migrations` ledger;
  - optional `psycopg` live connection via `CELL_DATABASE_URL` or `DATABASE_URL`;
  - dry-run summary for offline validation.

- `infra/datastores/postgres/migrations/cell/0001_personal_intelligence_cell.sql`
  - control-plane schema for cell runtime records.
  - canonical payload is stored in `body JSONB NOT NULL`.
  - generated columns expose queryable/indexable fields.

## Operator commands

Dry-run migration plan without a database:

```bash
PYTHONPATH=apps/cell-service/src python3 -m cell_service.cli postgres-plan
```

Plan against a live database:

```bash
CELL_DATABASE_URL='postgresql://user:pass@localhost:5432/prophet' \
PYTHONPATH=apps/cell-service/src python3 -m cell_service.cli postgres-plan
```

Apply migrations:

```bash
CELL_DATABASE_URL='postgresql://user:pass@localhost:5432/prophet' \
PYTHONPATH=apps/cell-service/src python3 -m cell_service.cli postgres-migrate
```

Replay the cell loop against Postgres after applying migrations:

```bash
CELL_DATABASE_URL='postgresql://user:pass@localhost:5432/prophet' \
PYTHONPATH=apps/cell-service/src python3 -m cell_service.cli replay-loop --postgres --migrate-first --summary
```

## Body-first table shape

The repository writes only the object key and canonical JSON body:

```sql
INSERT INTO <table> (<key>, body)
VALUES (%s, %s::jsonb)
ON CONFLICT (<key>) DO UPDATE SET body = EXCLUDED.body
```

The migration exposes generated columns over that body for queryability. This avoids keeping two competing sources of truth while still allowing indexes over cell, watch, signal, feed, intent, feedback, archive, and evidence metadata.

## Ordering constraints

The current replay path writes resources in dependency order:

```text
Cell -> CellConfig -> Source -> Watch -> WatchPattern -> Signal -> FeedItem -> IntentEvent -> FeedbackEvent -> CellArchive
```

Generated foreign-key columns rely on that order. Future bulk import/restore tooling must preserve the same dependency order or use a staged restore process.

## Known limitations

- Live Postgres tests are not yet part of CI.
- `psycopg` is optional and not pinned in `requirements-test.txt`.
- ClickHouse analytical fact emission is not yet implemented.
- Gateway/API binding is not yet implemented.
- Restore is still represented as `CellArchive` metadata and dry-run references, not a full restore executor.

## Validation

The following local validators cover this lane without requiring a live database:

```bash
python3 tools/validate_cell_postgres_runtime.py
python3 tools/validate_personal_intelligence_cell.py
python3 tools/smoke_cell_service_loop.py
```

Full repo validation reaches the same lane through:

```bash
make validate-repo
```
