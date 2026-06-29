"""
prophet-agent-session: developer-facing session API for the SocioProphet governed model stack.

Quick start:

    from agent_session import AgentSession, Reasoning
    from agent_session.schema import generable
    from pydantic import BaseModel

    session = AgentSession()
    response = await session.respond("Plan a 4-day trip to Tokyo.")

    @generable
    class Trip(BaseModel):
        destination: str
        days: int
        highlights: list[str]

    result = await session.respond("Plan a trip to Kyoto.", generating=Trip)
    print(result.destination)

    async for chunk in session.stream("Summarise the news."):
        print(chunk, end="", flush=True)

Environment variables:
    PROPHET_LOCAL_BASE_URL     Ollama base URL (default http://localhost:11435)
    PROPHET_LIGHT_MODEL        Model for LIGHT lane    (default llama3.2:1b)
    PROPHET_MODERATE_MODEL     Model for MODERATE lane (default qwen3:14b)
    PROPHET_DEEP_MODEL         Model for DEEP lane     (default qwen3:14b)
    PROPHET_HOSTED_MODEL       Hosted model for DEEP fallback (default claude-sonnet-4-6)
    ANTHROPIC_API_KEY          Enables hosted fallback on DEEP lane
"""
from .session import AgentSession
from .reasoning import Reasoning, RoutePolicy
from .schema import generable

__all__ = ["AgentSession", "Reasoning", "RoutePolicy", "generable"]
