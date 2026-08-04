from __future__ import annotations

import uuid
from typing import Any

import httpx

from . import config


class MatrixClient:
    """Thin async client for the Matrix Client-Server API."""

    def __init__(
        self,
        homeserver_url: str = config.HOMESERVER_URL,
        access_token: str = config.ACCESS_TOKEN,
    ) -> None:
        self._base = homeserver_url.rstrip("/")
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @staticmethod
    def _txn_id() -> str:
        return uuid.uuid4().hex

    async def send_message(
        self,
        room_id: str,
        body: str,
        thread_event_id: str | None = None,
    ) -> str:
        """Send a plain-text m.room.message to a room. Returns the new event_id."""
        content: dict[str, Any] = {"msgtype": "m.text", "body": body}
        if thread_event_id:
            content["m.relates_to"] = {
                "rel_type": "m.thread",
                "event_id": thread_event_id,
            }
        return await self._send_event(room_id, "m.room.message", content)

    async def send_code_block(
        self,
        room_id: str,
        code: str,
        lang: str = "",
        thread_event_id: str | None = None,
    ) -> str:
        """Send a formatted code block as m.room.message."""
        lang_class = f' class="language-{lang}"' if lang else ""
        formatted_body = f"<pre><code{lang_class}>{code}</code></pre>"
        content: dict[str, Any] = {
            "msgtype": "m.text",
            "body": f"```{lang}\n{code}\n```",
            "format": "org.matrix.custom.html",
            "formatted_body": formatted_body,
        }
        if thread_event_id:
            content["m.relates_to"] = {
                "rel_type": "m.thread",
                "event_id": thread_event_id,
            }
        return await self._send_event(room_id, "m.room.message", content)

    async def react(self, room_id: str, event_id: str, emoji: str) -> None:
        """Send an m.reaction to an event."""
        content: dict[str, Any] = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji,
            }
        }
        await self._send_event(room_id, "m.reaction", content)

    async def _send_event(
        self, room_id: str, event_type: str, content: dict[str, Any]
    ) -> str:
        txn_id = self._txn_id()
        url = (
            f"{self._base}/_matrix/client/v3/rooms/{room_id}"
            f"/send/{event_type}/{txn_id}"
        )
        async with httpx.AsyncClient() as http:
            resp = await http.put(url, json=content, headers=self._headers())
            resp.raise_for_status()
            return resp.json()["event_id"]
