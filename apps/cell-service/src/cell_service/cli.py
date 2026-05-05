from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .service import CellService

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal Intelligence Cell service smoke CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Print cell-service health status")

    replay = sub.add_parser("replay-loop", help="Replay a governed Personal Intelligence Cell loop contract")
    replay.add_argument("--contract", type=Path, default=DEFAULT_LOOP_CONTRACT)
    replay.add_argument("--summary", action="store_true", help="Print compact summary instead of full replay output")

    args = parser.parse_args()
    service = CellService()

    if args.command == "health":
        print(json.dumps(service.health(), indent=2, sort_keys=True))
        return

    if args.command == "replay-loop":
        loop = load_json(args.contract)
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
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
