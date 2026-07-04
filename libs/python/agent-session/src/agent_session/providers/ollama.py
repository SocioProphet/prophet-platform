from __future__ import annotations

import json
import os
from typing import AsyncIterator

import httpx

from .base import Provider, ProviderResponse

_DEFAULT_BASE_URL = "http://localhost:11435"
_DEFAULT_MODEL = "qwen3:14b"

# Effort → Ollama num_predict budget (rough mapping; models ignore if unsupported)
_EFFORT_TOKENS: dict[str, int] = {
    "low":    512,
    "medium": 2048,
    "high":   4096,
}


class OllamaProvider(Provider):
    def __init__(self, model: str, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("PROPHET_LOCAL_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

    async def respond(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema_instruction: str | None = None,
        effort: str = "medium",
    ) -> ProviderResponse:
        messages = self._build_messages(prompt, system, schema_instruction)
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": _EFFORT_TOKENS.get(effort, 2048)},
        }
        if schema_instruction:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return ProviderResponse(
            content=choice["content"],
            model=data.get("model", self.model),
            provider="ollama",
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        effort: str = "medium",
    ) -> AsyncIterator[str]:
        messages = self._build_messages(prompt, system, None)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": _EFFORT_TOKENS.get(effort, 2048)},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:]
                    if payload_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload_str)
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError):
                        continue

    @staticmethod
    def _build_messages(
        prompt: str,
        system: str | None,
        schema_instruction: str | None,
    ) -> list[dict]:
        messages = []
        sys_parts = []
        if system:
            sys_parts.append(system)
        if schema_instruction:
            sys_parts.append(schema_instruction)
        if sys_parts:
            messages.append({"role": "system", "content": "\n\n".join(sys_parts)})
        messages.append({"role": "user", "content": prompt})
        return messages

    @classmethod
    def from_env(cls, model_env_key: str, effort: str = "medium") -> "OllamaProvider":
        model = os.getenv(model_env_key, _DEFAULT_MODEL)
        return cls(model=model)
