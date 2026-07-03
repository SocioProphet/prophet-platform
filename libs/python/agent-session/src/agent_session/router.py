from __future__ import annotations

import os

from .reasoning import Reasoning, RoutePolicy, lane_for
from .providers.base import Provider
from .providers.ollama import OllamaProvider
from .providers.anthropic import AnthropicProvider

_HOSTED_MODEL_ENV = "PROPHET_HOSTED_MODEL"
_HOSTED_MODEL_DEFAULT = "claude-sonnet-4-6"


def resolve(
    reasoning: Reasoning,
    policy: RoutePolicy | None,
) -> tuple[Provider, str]:
    """
    Returns (provider, effort) for the given reasoning level and policy.

    Resolution order:
      1. Route policy overrides (LOCAL_ONLY blocks hosted; HOSTED_OK enables it at MODERATE+)
      2. Reasoning lane defaults from agent-execution-model-routing-policy
      3. Hosted fallback only when ANTHROPIC_API_KEY is set and lane allows it
    """
    model_env_key, hosted_allowed, effort = lane_for(reasoning, policy)
    local_model = os.getenv(model_env_key, _default_local_model(reasoning))

    if hosted_allowed and os.getenv("ANTHROPIC_API_KEY"):
        # DEEP with a key: prefer local, accept hosted as fallback.
        # Return local for now; session handles fallback on error.
        # The router just advertises both options via a FallbackProvider.
        return FallbackProvider(
            primary=OllamaProvider(model=local_model),
            fallback=AnthropicProvider(model=os.getenv(_HOSTED_MODEL_ENV, _HOSTED_MODEL_DEFAULT)),
        ), effort

    return OllamaProvider(model=local_model), effort


def _default_local_model(reasoning: Reasoning) -> str:
    defaults = {
        Reasoning.LIGHT:    os.getenv("PROPHET_LIGHT_MODEL",    "llama3.2:1b"),
        Reasoning.MODERATE: os.getenv("PROPHET_MODERATE_MODEL", "qwen3:14b"),
        Reasoning.DEEP:     os.getenv("PROPHET_DEEP_MODEL",     "qwen3:14b"),
        Reasoning.SOVEREIGN: os.getenv("PROPHET_MODERATE_MODEL","qwen3:14b"),
    }
    return defaults[reasoning]


class FallbackProvider(Provider):
    """
    Tries primary first; on transport/HTTP error falls back to secondary.
    Only used for DEEP reasoning when a hosted key is present.
    """
    def __init__(self, primary: Provider, fallback: Provider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def respond(self, prompt, *, system=None, schema_instruction=None, effort="high"):
        try:
            return await self._primary.respond(
                prompt, system=system, schema_instruction=schema_instruction, effort=effort
            )
        except Exception:
            return await self._fallback.respond(
                prompt, system=system, schema_instruction=schema_instruction, effort=effort
            )

    async def stream(self, prompt, *, system=None, effort="high"):
        try:
            async for chunk in self._primary.stream(prompt, system=system, effort=effort):
                yield chunk
        except Exception:
            async for chunk in self._fallback.stream(prompt, system=system, effort=effort):
                yield chunk
