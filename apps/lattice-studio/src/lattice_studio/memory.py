"""Memory mesh sidecars for Lattice Studio activity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class MemoryEvent:
    memory_event_id: str
    subject_ref: str
    event_type: str
    summary: str
    links: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "memory.socioprophet.dev/v1",
            "kind": "MemoryEvent",
            "memoryEventId": self.memory_event_id,
            "subjectRef": self.subject_ref,
            "eventType": self.event_type,
            "summary": self.summary,
            "links": self.links,
            "createdAt": self.created_at,
        }


def memory_event(*, subject_ref: str, event_type: str, summary: str, links: list[str] | None = None) -> MemoryEvent:
    seed = json.dumps(
        {"subjectRef": subject_ref, "eventType": event_type, "summary": summary, "links": sorted(links or [])},
        sort_keys=True,
        separators=(",", ":"),
    )
    return MemoryEvent(
        memory_event_id="memory-event:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        subject_ref=subject_ref,
        event_type=event_type,
        summary=summary,
        links=sorted(links or []),
    )


def memory_event_set(events: list[MemoryEvent]) -> dict[str, Any]:
    return {
        "apiVersion": "memory.socioprophet.dev/v1",
        "kind": "MemoryEventSet",
        "events": [event.to_dict() for event in events],
    }
