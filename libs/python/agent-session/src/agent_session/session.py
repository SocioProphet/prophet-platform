"""
AgentSession — the developer-facing session API for the SocioProphet governed model stack.

Mirrors Apple Foundation Models' LanguageModelSession: one object, same API regardless
of whether the backend is a local Ollama model or a hosted provider.

    session = AgentSession()
    response = await session.respond("Plan a 4-day trip to Tokyo.")

    session = AgentSession(reasoning=Reasoning.DEEP)
    response = await session.respond("Analyse the competitive landscape.")

    @generable
    class Trip(BaseModel):
        destination: str
        days: int

    result = await session.respond("Plan a trip to Tokyo.", generating=Trip)
    print(result.destination)

    async for chunk in session.stream("Summarise today's news."):
        print(chunk, end="", flush=True)
"""
from __future__ import annotations

from typing import AsyncIterator, TypeVar, overload

from pydantic import BaseModel

from .reasoning import Reasoning, RoutePolicy
from .router import resolve
from .schema import is_generable, schema_instruction, parse_response
from .providers.base import ProviderResponse

T = TypeVar("T", bound=BaseModel)


class AgentSession:
    """
    A stateless session over the governed model stack.

    Args:
        reasoning: Depth hint that maps onto a routing lane.
            LIGHT    → local-cheap (fast, small model)
            MODERATE → local standard (default)
            DEEP     → local → hosted fallback when key present
            SOVEREIGN → local-only regardless of depth
        system: Optional system prompt prepended to every request.
        policy: Hard routing override (LOCAL_ONLY, LOCAL_FIRST, HOSTED_OK).
    """

    def __init__(
        self,
        reasoning: Reasoning = Reasoning.MODERATE,
        system: str | None = None,
        policy: RoutePolicy | None = None,
    ) -> None:
        self._reasoning = reasoning
        self._system = system
        self._policy = policy
        self._provider, self._effort = resolve(reasoning, policy)

    @overload
    async def respond(self, prompt: str) -> str:
        pass
    @overload
    async def respond(self, prompt: str, *, generating: type[T]) -> T:
        pass

    async def respond(self, prompt: str, *, generating: type[T] | None = None) -> str | T:
        """
        Generate a response for prompt.

        When generating= is provided the model is instructed to return a JSON
        object conforming to that Pydantic model's schema, and the result is
        parsed into an instance of that type.
        """
        schema_hint: str | None = None
        if generating is not None:
            if not is_generable(generating):
                raise TypeError(
                    f"{generating.__name__} must be decorated with @generable "
                    "to be used as a structured output target."
                )
            schema_hint = schema_instruction(generating)

        result: ProviderResponse = await self._provider.respond(
            prompt,
            system=self._system,
            schema_instruction=schema_hint,
            effort=self._effort,
        )

        if generating is not None:
            return parse_response(generating, result.content)
        return result.content

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield response text incrementally."""
        async for chunk in self._provider.stream(
            prompt, system=self._system, effort=self._effort
        ):
            yield chunk
