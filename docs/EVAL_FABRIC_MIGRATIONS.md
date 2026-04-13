# Eval Fabric Migrations

This document defines the **current migration/versioning path** for the evaluation fabric lane.

## Why this exists

The bootstrap lane started with ordered SQL files under:
- `infra/datastores/postgres/`
- `infra/datastores/clickhouse/`

That was acceptable for first bring-up, but it is not a sufficient long-term migration strategy. We need a repeatable runner and bookkeeping tables so platform operators can tell which migrations have already been applied.

## Current migration runner

Use:
- `tools/eval_fabric_migrate.py`
- `tools/requirements-eval-fabric-migrate.txt`

The runner:
- scans ordered `NNN_*.sql` files in the Postgres and ClickHouse datastore directories
- creates `schema_migrations` bookkeeping tables when missing
- applies only unapplied migration files
- records each applied migration name after successful execution

## Environment variables

Postgres:
- `POSTGRES_DSN`

ClickHouse:
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_PORT`
- `CLICKHOUSE_DATABASE`

## Example local invocation

```bash
cd "$HOME/dev/prophet-platform" && python3 -m venv .venv && source .venv/bin/activate && pip install -r tools/requirements-eval-fabric-migrate.txt && python tools/eval_fabric_migrate.py
```

## Notes

This is an interim platform migration strategy.

Next step after this lands:
1. promote the runner into a more formal migration workflow
2. wire migration execution into local and CI setup paths
3. decide whether to keep this lightweight runner or move to a dedicated migration tool for Postgres while retaining a parallel ClickHouse migration path
