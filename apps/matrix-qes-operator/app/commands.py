from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OperatorCommand:
    verb: str
    args: list[str]
    actor: str
    room_id: str
    thread_id: str | None = None


def parse_command(*, actor: str, room_id: str, thread_id: str | None, body: str) -> OperatorCommand:
    tokens = body.strip().split()
    if not tokens or tokens[0] != "!qes":
        raise ValueError("Command must start with !qes")
    if len(tokens) == 1:
        raise ValueError("Missing command verb")
    return OperatorCommand(
        verb=tokens[1],
        args=tokens[2:],
        actor=actor,
        room_id=room_id,
        thread_id=thread_id,
    )
