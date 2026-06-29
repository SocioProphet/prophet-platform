from __future__ import annotations

import json
import os
from typing import AsyncIterator

import httpx

from .base import Provider, ProviderResponse

_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-4-6"

_EFFORT_TO_THINKING: dict[str, dict] = {
    "low":    {"type": "disabled"},
    "medium": {"type": "disabled"},
    "high":   {"type": "enabled", "budget_tokens": 10000},
}

_EFFORT_MAX_TOKENS: dict[str, int] = {
    "low":    1024,
    "medium": 4096,
    "high":   8192,
}


class AnthropicProvider(Provider):
    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = _API_URL,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = base_url
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_payload(
        self,
        prompt: str,
        system: str | None,
        schema_instruction: str | None,
        effort: str,
        stream: bool,
    ) -> dict:
        sys_parts = []
        if system:
            sys_parts.append(system)
        if schema_instruction:
            sys_parts.append(schema_instruction)

        payload: dict = {
            "model": self.model,
            "max_tokens": _EFFORT_MAX_TOKENS.get(effort, 4096),
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_parts:
            payload["system"] = "\n\n".join(sys_parts)
        if stream:
            payload["stream"] = True
        thinking = _EFFORT_TO_THINKING.get(effort)
        if thinking and thinking.get("type") == "enabled":
            payload["thinking"] = thinking
        return payload

    async def respond(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema_instruction: str | None = None,
        effort: str = "medium",
    ) -> ProviderResponse:
        payload = self._build_payload(prompt, system, schema_instruction, effort, stream=False)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.base_url, headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()

        # Extract text blocks only; skip thinking blocks
        content = "".join(
            b["text"] for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        return ProviderResponse(
            content=content,
            model=data.get("model", self.model),
            provider="anthropic",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        effort: str = "medium",
    ) -> AsyncIterator[str]:
        payload = self._build_payload(prompt, system, None, effort, stream=True)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", self.base_url, headers=self._headers(), json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:]
                    if payload_str.strip() in ("[DONE]", ""):
                        continue
                    try:
                        event = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield text
