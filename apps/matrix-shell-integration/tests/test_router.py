from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.router import route_event


def _make_event(
    body: str,
    sender: str = "@alice:localhost",
    room_id: str = "!room1:localhost",
    event_id: str = "$evt1",
    event_type: str = "m.room.message",
) -> dict:
    return {
        "type": event_type,
        "sender": sender,
        "room_id": room_id,
        "event_id": event_id,
        "content": {"msgtype": "m.text", "body": body},
    }


def _make_client() -> MagicMock:
    client = MagicMock()
    client.send_message = AsyncMock(return_value="$reply1")
    client.react = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_qes_command_routed_to_operator():
    """!qes k3s get nodes is forwarded to operator /execute and reply sent back."""
    client = _make_client()
    event = _make_event("!qes k3s get nodes")

    operator_response = {"reply": "node1 Ready\nnode2 Ready"}

    with patch("app.router.httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http_cls.return_value.__aenter__.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = operator_response
        mock_http.post = AsyncMock(return_value=mock_resp)

        await route_event(event, client)

    # Verify operator was called with correct payload
    mock_http.post.assert_awaited_once()
    call_args = mock_http.post.call_args
    assert "/v1/matrix-qes/commands/execute" in call_args.args[0]
    payload = call_args.kwargs["json"]
    assert payload["body"] == "!qes k3s get nodes"
    assert payload["actor"] == "@alice:localhost"
    assert payload["room_id"] == "!room1:localhost"

    # Reply sent back threaded on original event
    client.send_message.assert_awaited_once()
    send_args = client.send_message.call_args
    assert send_args.args[1] == "node1 Ready\nnode2 Ready"
    assert send_args.kwargs.get("thread_event_id") == "$evt1"

    # Reacted with success emoji
    client.react.assert_awaited_once_with("!room1:localhost", "$evt1", "✅")


@pytest.mark.asyncio
async def test_non_qes_message_ignored():
    """Messages that do not start with !qes or !wormhole are silently ignored."""
    client = _make_client()
    event = _make_event("hello world")

    await route_event(event, client)

    client.send_message.assert_not_awaited()
    client.react.assert_not_awaited()


@pytest.mark.asyncio
async def test_wormhole_aliased_to_qes():
    """!wormhole send is rewritten to !qes wormhole send before forwarding."""
    client = _make_client()
    event = _make_event("!wormhole send payload")

    with patch("app.router.httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http_cls.return_value.__aenter__.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"reply": "wormhole opened"}
        mock_http.post = AsyncMock(return_value=mock_resp)

        await route_event(event, client)

    call_payload = mock_http.post.call_args.kwargs["json"]
    assert call_payload["body"] == "!qes wormhole send payload"


@pytest.mark.asyncio
async def test_operator_error_sends_failure_reaction():
    """When operator call fails, ❌ reaction and error message are sent."""
    client = _make_client()
    event = _make_event("!qes status")

    with patch("app.router.httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http_cls.return_value.__aenter__.return_value = mock_http
        mock_http.post = AsyncMock(side_effect=Exception("connection refused"))

        await route_event(event, client)

    client.react.assert_awaited_once_with("!room1:localhost", "$evt1", "❌")
    client.send_message.assert_awaited_once()
    msg_body = client.send_message.call_args.args[1]
    assert "connection refused" in msg_body


@pytest.mark.asyncio
async def test_non_message_event_ignored():
    """Non m.room.message events (e.g. m.room.member) are ignored."""
    client = _make_client()
    event = _make_event("!qes status", event_type="m.room.member")

    await route_event(event, client)

    client.send_message.assert_not_awaited()
    client.react.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_message_ignored():
    """Messages from the bot user itself are not re-processed."""
    client = _make_client()
    event = _make_event("!qes status", sender="@sourceos-bot:localhost")

    with patch("app.router.config.BOT_USER_ID", "@sourceos-bot:localhost"):
        await route_event(event, client)

    client.send_message.assert_not_awaited()
    client.react.assert_not_awaited()
