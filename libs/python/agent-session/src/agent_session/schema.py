"""
Structured output support — the @generable equivalent for Python/Pydantic.

Usage:
    from agent_session.schema import generable
    from pydantic import BaseModel

    @generable
    class Trip(BaseModel):
        destination: str
        days: int
        highlights: list[str]

    response = await session.respond("Plan a trip to Tokyo.", generating=Trip)
    # response is a Trip instance

The @generable decorator is a marker only — it adds no runtime behaviour beyond
tagging the class as schema-exportable. AgentSession detects it via is_generable().
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_GENERABLE_ATTR = "__agent_session_generable__"


def generable(cls: type[T]) -> type[T]:
    """Marks a Pydantic model as suitable for structured generation."""
    setattr(cls, _GENERABLE_ATTR, True)
    return cls


def is_generable(cls: Any) -> bool:
    return isinstance(cls, type) and issubclass(cls, BaseModel) and getattr(cls, _GENERABLE_ATTR, False)


def schema_instruction(cls: type[BaseModel]) -> str:
    """Returns a system-prompt fragment that instructs the model to emit valid JSON."""
    schema = cls.model_json_schema()
    schema_str = json.dumps(schema, indent=2)
    return (
        "Respond with a single JSON object that strictly conforms to the following JSON Schema. "
        "Do not include markdown fences, commentary, or any text outside the JSON object.\n\n"
        f"Schema:\n{schema_str}"
    )


def parse_response(cls: type[T], raw: str) -> T:
    """
    Parse a raw model response into an instance of cls.
    Strips markdown fences if present before attempting JSON parse.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()
    return cls.model_validate_json(text)
