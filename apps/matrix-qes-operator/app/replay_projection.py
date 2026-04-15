from __future__ import annotations

from typing import Any
from uuid import uuid4


def operator_action_to_replay_request(*, tenant_id: str, producer: str, actor_id: str, room_id: str, thread_id: str | None, args: list[str]) -> dict[str, Any]:
    dry_run = "dry-run" in args
    scope_ref = f"matrix://{room_id}/{thread_id or 'main'}"
    return {
        "request_id": str(uuid4()),
        "emitted_at": "1970-01-01T00:00:00+00:00",
        "tenant_id": tenant_id,
        "producer": producer,
        "requested_by": actor_id,
        "scope_ref": scope_ref,
        "reason": "matrix_operator_replay_request",
        "room_id": room_id,
        "thread_id": thread_id,
        "workflow_hint": "qes.replay",
        "dry_run": dry_run,
        "notes": {"args": args},
    }
