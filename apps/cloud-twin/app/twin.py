"""Cloud-Twin lifecycle — instantiate a verified Twin from a GenesisSeed and emit
a replayable TwinEventEnvelope stream (the K3 twin-bridge lifecycle).

Read-only / no-op skeleton (genesis plan Phase-1 exit criteria): a seed becomes a
verified twin end to end, a no-op adapter "executes", and the event stream
reconstructs the lifecycle. World-changing actuation is gated behind later phases.
Contracts are the merged canonical schemas (sourceos-spec: GenesisSeed,
TwinEventEnvelope), vendored under schemas/.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
_GENESIS_SEED = json.loads((_SCHEMA_DIR / "GenesisSeed.json").read_text(encoding="utf-8"))
_TWIN_EVENT = json.loads((_SCHEMA_DIR / "TwinEventEnvelope.json").read_text(encoding="utf-8"))
_seed_validator = jsonschema.Draft202012Validator(_GENESIS_SEED)
_event_validator = jsonschema.Draft202012Validator(_TWIN_EVENT)

# The K3 verified-twin lifecycle for a read-only/no-op twin.
LIFECYCLE = ("twin.created", "twin.authorized", "twin.verified")


class SeedValidationError(ValueError):
    """A GenesisSeed that does not conform to the canonical schema."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_seed(seed: dict[str, Any]) -> None:
    errors = sorted(_seed_validator.iter_errors(seed), key=lambda e: list(e.path))
    if errors:
        loc = ".".join(str(p) for p in errors[0].path) or "<root>"
        raise SeedValidationError(f"GenesisSeed invalid at {loc}: {errors[0].message}")


class Twin:
    def __init__(self, twin_id: str, seed: dict[str, Any], actor_id: str):
        self.twin_id = twin_id
        self.seed = seed
        self.actor_id = actor_id
        self.state = "created"
        self.events: list[dict[str, Any]] = []

    def _emit(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        evt = {
            "type": "TwinEventEnvelope",
            "event_id": f"evt:{uuid.uuid4()}",
            "event_type": event_type,
            "timestamp": _now(),
            "actor_id": self.actor_id,
            "twin_id": self.twin_id,
            "policy_refs": list(self.seed.get("policy_profile", [])) or ["policy:twin/default"],
            "provenance_refs": [f"prov:cloud-twin:{self.twin_id}"],
            "payload": payload,
        }
        # Fail closed: never emit an envelope that violates the contract.
        jsonschema.validate(evt, _TWIN_EVENT)
        self.events.append(evt)
        return evt

    def run_lifecycle(self) -> None:
        self._emit("twin.created", {"archetype": self.seed.get("archetype")})
        self.state = "authorized"
        self._emit("twin.authorized", {"policy_profile": self.seed.get("policy_profile", [])})
        # No-op / read-only "execution": only read-capable organs run in the skeleton.
        self.state = "verified"
        self._emit(
            "twin.verified",
            {"status": "verified", "capabilities": ["dry_run", "status"], "organs": self.seed.get("organs_allowed", [])},
        )


class TwinRegistry:
    """In-memory twin store (Phase-1 skeleton; durable K3 workflow is Phase-1+)."""

    def __init__(self) -> None:
        self._twins: dict[str, Twin] = {}

    def instantiate(self, seed: dict[str, Any], actor_id: str) -> Twin:
        validate_seed(seed)
        twin_id = f"twin:{seed['archetype']}/{uuid.uuid4().hex[:8]}"
        twin = Twin(twin_id, seed, actor_id)
        twin.run_lifecycle()
        self._twins[twin_id] = twin
        return twin

    def get(self, twin_id: str) -> Twin | None:
        return self._twins.get(twin_id)

    def count(self) -> int:
        return len(self._twins)
