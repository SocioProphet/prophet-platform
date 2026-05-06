from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .postgres_migrations import apply_migrations, connect_postgres, dry_run_summary, migration_plan
from .postgres_repository import PostgresCellRepository
from .service import CellService

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def service_from_args(args: argparse.Namespace) -> CellService:
    if getattr(args, "postgres", False):
        connection = connect_postgres(getattr(args, "database_url", None))
        return CellService(repository=PostgresCellRepository(connection))
    return CellService()


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal Intelligence Cell service smoke CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Print cell-service health status")
    health.add_argument("--postgres", action="store_true", help="Use Postgres repository via CELL_DATABASE_URL/DATABASE_URL")
    health.add_argument("--database-url", help="Postgres database URL")

    replay = sub.add_parser("replay-loop", help="Replay a governed Personal Intelligence Cell loop contract")
    replay.add_argument("--contract", type=Path, default=DEFAULT_LOOP_CONTRACT)
    replay.add_argument("--summary", action="store_true", help="Print compact summary instead of full replay output")
    replay.add_argument("--postgres", action="store_true", help="Use Postgres repository via CELL_DATABASE_URL/DATABASE_URL")
    replay.add_argument("--database-url", help="Postgres database URL")
    replay.add_argument("--migrate-first", action="store_true", help="Apply Postgres migrations before replay")

    plan = sub.add_parser("postgres-plan", help="Print Postgres migration plan without applying it")
    plan.add_argument("--database-url", help="Optional Postgres database URL; when omitted, all migrations are reported unapplied")

    migrate = sub.add_parser("postgres-migrate", help="Apply cell-service Postgres migrations")
    migrate.add_argument("--database-url", help="Postgres database URL")

    args = parser.parse_args()

    if args.command == "health":
        service = service_from_args(args)
        print_json(service.health())
        return

    if args.command == "postgres-plan":
        if args.database_url:
            connection = connect_postgres(args.database_url)
            print_json({"ok": True, "mode": "connected", "migrations": [item.__dict__ for item in migration_plan(connection)]})
        else:
            print_json(dry_run_summary())
        return

    if args.command == "postgres-migrate":
        connection = connect_postgres(args.database_url)
        print_json({"ok": True, "migrations": [item.__dict__ for item in apply_migrations(connection)]})
        return

    if args.command == "replay-loop":
        if args.postgres and args.migrate_first:
            apply_migrations(connect_postgres(args.database_url))
        loop = load_json(args.contract)
        service = service_from_args(args)
        result = service.run_loop_contract(loop)
        if args.summary:
            summary = {
                "status": "ok",
                "cell_id": result["cell"]["id"],
                "watch_id": result["watch"]["id"],
                "signal_id": result["signal"]["id"],
                "feed_item_id": result["feed_item"]["id"],
                "intent_event_id": result["intent_event"]["id"],
                "feedback_event_id": result["feedback_event"]["id"],
                "cell_archive_id": result["cell_archive"]["id"],
                "private_feed_items": result["private_feed"]["item_count"],
                "publication_surfaces": sorted(result["publication_bundle"].keys()),
            }
            print_json(summary)
        else:
            print_json(result)
        return

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
