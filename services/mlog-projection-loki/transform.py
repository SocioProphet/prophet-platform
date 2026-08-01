"""Pure, testable core of the Loki projection.

Maps a CDM EventEnvelope (the Map-Log record) to a Loki push payload. Kept free
of Kafka/HTTP so it can be unit-tested deterministically. Loki is a *projection*
rebuilt from the log — this function is the projection rule.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone

# Loki labels must be low-cardinality; everything else stays in the log line.
_LABEL_KEYS = ("type", "source", "topic", "namespace")


def _to_ns(ts: str | int | None) -> str:
    """EventEnvelope.time (RFC3339) or epoch → Loki nanosecond string."""
    if ts is None:
        return str(int(datetime.now(timezone.utc).timestamp() * 1e9))
    if isinstance(ts, (int, float)):
        return str(int(ts * 1e9)) if ts < 1e12 else str(int(ts))
    s = ts.replace("Z", "+00:00")
    return str(int(datetime.fromisoformat(s).timestamp() * 1e9))


def envelope_to_loki_stream(env: dict) -> dict:
    """CDM EventEnvelope -> Loki push body ({"streams":[...]}).

    Idempotency: the stream carries the envelope id as a structured-metadata-free
    label-free field inside the line, so replays produce identical bytes.
    """
    if "id" not in env or "type" not in env:
        raise ValueError("not an EventEnvelope: missing id/type")
    labels = {k: str(env[k]) for k in _LABEL_KEYS if env.get(k)}
    labels.setdefault("source_kind", "mlog-projection")
    line = json.dumps(
        {"id": env["id"], "subject": env.get("subject"), "payload": env.get("payload")},
        separators=(",", ":"), sort_keys=True,
    )
    return {"streams": [{"stream": labels, "values": [[_to_ns(env.get("time")), line]]}]}
