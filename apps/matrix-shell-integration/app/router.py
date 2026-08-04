from __future__ import annotations

import logging

import httpx

from . import config
from .homeserver import MatrixClient

logger = logging.getLogger(__name__)

_WORMHOLE_PREFIX = "!wormhole"
_QES_PREFIX = "!qes"


async def route_event(event: dict, client: MatrixClient) -> None:
    """Process one Matrix room event from the homeserver push."""
    # Only handle room messages
    if event.get("type") != "m.room.message":
        return

    content = event.get("content", {})
    body: str = content.get("body", "")
    room_id: str = event.get("room_id", "")
    sender: str = event.get("sender", "")
    event_id: str = event.get("event_id", "")

    if not body or not room_id:
        return

    # Ignore messages from the bot itself
    if sender == config.BOT_USER_ID:
        return

    # Normalise !wormhole alias → !qes wormhole …
    if body.startswith(_WORMHOLE_PREFIX):
        rest = body[len(_WORMHOLE_PREFIX):].strip()
        body = f"!qes wormhole {rest}" if rest else "!qes wormhole"

    if not body.startswith(_QES_PREFIX):
        return

    # Forward to the QES operator execute endpoint
    payload = {
        "actor": sender,
        "room_id": room_id,
        "thread_id": event_id,
        "body": body,
    }
    execute_url = f"{config.OPERATOR_URL}/v1/matrix-qes/commands/execute"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(execute_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            reply: str = data.get("reply", data.get("message", str(data)))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Operator call failed for event %s: %s", event_id, exc)
        await client.react(room_id, event_id, "❌")
        await client.send_message(
            room_id,
            f"⚠️ QES operator error: {exc}",
            thread_event_id=event_id,
        )
        return

    await client.react(room_id, event_id, "✅")
    await client.send_message(room_id, reply, thread_event_id=event_id)
