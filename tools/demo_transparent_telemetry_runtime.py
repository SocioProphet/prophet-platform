#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "evidence-receipts"))

from app.telemetry_runtime import emit_event_bundle  # type: ignore


def main() -> None:
    result = emit_event_bundle(
        "telemetry-runtime",
        "reliability.conversation.stream.completed",
        {
            "request_id": "req-demo-001",
            "local_turn_id": "turn-demo-001",
            "duration_ms_bucket": 4200,
            "stream_transport": "sse_like",
            "completion_status": "clean_final_message",
            "subject_ref": "turn://turn-demo-001",
        },
        control_snapshot={"product_analytics": "disabled"},
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
