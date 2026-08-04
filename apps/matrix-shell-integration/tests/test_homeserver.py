from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.homeserver import MatrixClient


def _make_client(homeserver_url: str = "http://hs.test:8448", token: str = "tok") -> MatrixClient:
    return MatrixClient(homeserver_url=homeserver_url, access_token=token)


def _mock_http_put(event_id: str = "$new_event") -> tuple[AsyncMock, MagicMock]:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"event_id": event_id}
    mock_http = AsyncMock()
    mock_http.put = AsyncMock(return_value=mock_resp)
    return mock_http, mock_resp


@pytest.mark.asyncio
async def test_send_message_builds_correct_put_url():
    """send_message PUTs to /_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn}."""
    client = _make_client()
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http

        result = await client.send_message("!room1:localhost", "hello")

    assert result == "$new_event"
    mock_http.put.assert_awaited_once()
    url = mock_http.put.call_args.args[0]
    assert "/_matrix/client/v3/rooms/!room1:localhost/send/m.room.message/" in url
    assert "http://hs.test:8448" in url

    # Verify Authorization header
    headers = mock_http.put.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_send_message_includes_bearer_token():
    """Authorization header is set to Bearer <access_token>."""
    client = _make_client(token="secret_token")
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.send_message("!room:localhost", "hi")

    headers = mock_http.put.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret_token"


@pytest.mark.asyncio
async def test_thread_reply_includes_m_relates_to():
    """When thread_event_id is given, m.relates_to with rel_type=m.thread is included."""
    client = _make_client()
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.send_message("!room:localhost", "reply", thread_event_id="$orig")

    body = mock_http.put.call_args.kwargs["json"]
    assert "m.relates_to" in body
    relates = body["m.relates_to"]
    assert relates["rel_type"] == "m.thread"
    assert relates["event_id"] == "$orig"


@pytest.mark.asyncio
async def test_send_message_no_thread_omits_relates_to():
    """Without thread_event_id, m.relates_to must not appear in the content."""
    client = _make_client()
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.send_message("!room:localhost", "standalone")

    body = mock_http.put.call_args.kwargs["json"]
    assert "m.relates_to" not in body


@pytest.mark.asyncio
async def test_send_code_block_sets_formatted_body():
    """send_code_block includes format and formatted_body with <pre><code> wrapper."""
    client = _make_client()
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.send_code_block("!room:localhost", "ls -la", lang="bash")

    body = mock_http.put.call_args.kwargs["json"]
    assert body["format"] == "org.matrix.custom.html"
    assert '<code class="language-bash">' in body["formatted_body"]
    assert "ls -la" in body["formatted_body"]


@pytest.mark.asyncio
async def test_react_sends_annotation():
    """react() PUTs an m.reaction event with m.annotation rel_type."""
    client = _make_client()
    mock_http, _ = _mock_http_put()

    with patch("app.homeserver.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_http
        await client.react("!room:localhost", "$orig_event", "✅")

    url = mock_http.put.call_args.args[0]
    assert "/send/m.reaction/" in url

    body = mock_http.put.call_args.kwargs["json"]
    relates = body["m.relates_to"]
    assert relates["rel_type"] == "m.annotation"
    assert relates["event_id"] == "$orig_event"
    assert relates["key"] == "✅"
