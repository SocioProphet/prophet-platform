from __future__ import annotations

from typing import Any

from . import client


def get_recent_telemetry_view(service: str = "telemetry-runtime", limit: int = 25) -> dict[str, Any]:
    items = client.get_recent_receipts(service=service, limit=limit)
    return {
        "service": service,
        "items": items,
    }
