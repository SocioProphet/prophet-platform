"""
Session tests using unittest.mock to patch httpx.AsyncClient. No live network calls.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from agent_session import AgentSession, Reasoning, generable


@generable
class Summary(BaseModel):
    title: str
    body: str


def _ollama_response(content: str) -> dict:
    return {
        "model": "qwen3:14b",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


def _mock_ollama_client(content: str):
    """Returns a context-manager-compatible mock httpx.AsyncClient."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _ollama_response(content)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_respond_returns_string() -> None:
    mock_client = _mock_ollama_client("Hello, world.")
    with patch("agent_session.providers.ollama.httpx.AsyncClient", return_value=mock_client):
        session = AgentSession(reasoning=Reasoning.MODERATE)
        result = await session.respond("Say hello.")
    assert result == "Hello, world."


@pytest.mark.asyncio
async def test_respond_structured_output() -> None:
    raw = json.dumps({"title": "Test", "body": "Body text."})
    mock_client = _mock_ollama_client(raw)
    with patch("agent_session.providers.ollama.httpx.AsyncClient", return_value=mock_client):
        session = AgentSession(reasoning=Reasoning.LIGHT)
        result = await session.respond("Summarise something.", generating=Summary)
    assert isinstance(result, Summary)
    assert result.title == "Test"
    assert result.body == "Body text."


@pytest.mark.asyncio
async def test_respond_rejects_non_generable() -> None:
    class Plain(BaseModel):
        x: str

    session = AgentSession()
    with pytest.raises(TypeError, match="@generable"):
        await session.respond("x", generating=Plain)


@pytest.mark.asyncio
async def test_light_reasoning_uses_light_model(monkeypatch) -> None:
    monkeypatch.setenv("PROPHET_LIGHT_MODEL", "llama3.2:1b")
    captured: dict = {}

    async def fake_post(url, *, json=None, **kwargs):
        captured["body"] = json
        return _mock_ollama_client("ok").post.return_value

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    # raise_for_status on the returned mock response
    mock_client.post.return_value = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value=_ollama_response("ok")),
    )

    with patch("agent_session.providers.ollama.httpx.AsyncClient", return_value=mock_client):
        session = AgentSession(reasoning=Reasoning.LIGHT)
        await session.respond("hello")
    assert captured.get("body", {}).get("model") == "llama3.2:1b"


@pytest.mark.asyncio
async def test_system_prompt_included_in_request() -> None:
    captured: dict = {}

    async def fake_post(url, *, json=None, **kwargs):
        captured["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = _ollama_response("ok")
        return resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("agent_session.providers.ollama.httpx.AsyncClient", return_value=mock_client):
        session = AgentSession(system="You are a concise assistant.")
        await session.respond("hello")

    messages = captured["body"]["messages"]
    assert messages[0]["role"] == "system"
    assert "concise assistant" in messages[0]["content"]
