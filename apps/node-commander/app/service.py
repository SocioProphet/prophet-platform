from __future__ import annotations

from datetime import datetime, timezone


def get_status_view() -> dict:
    return {
        "service": "node-commander",
        "mode": "bootstrap",
        "placement_order": [
            "local",
            "trusted-private",
            "attested-fog",
            "burst-cloud"
        ],
        "runtime": {
            "container_runtime": "podman",
            "service_scope": "user"
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_heartbeat_view() -> dict:
    return {
        "service": "node-commander",
        "heartbeat": "ok",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
