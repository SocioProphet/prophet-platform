from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Provider(ABC):
    @abstractmethod
    async def respond(
        self,
        prompt: str,
        *,
        system: str | None = None,
        schema_instruction: str | None = None,
        effort: str = "medium",
    ) -> ProviderResponse:
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        effort: str = "medium",
    ) -> AsyncIterator[str]:
        pass
