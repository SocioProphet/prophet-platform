"""The vendored MarketDataEvent contract: tick → event constructor + hermetic validation.

Schema provenance (vendored so validation needs no network and no spec checkout):
    repo    SourceOS-Linux/sourceos-spec  (merged PR #204)
    path    schemas/MarketDataEvent.json
    commit  487e4b614b79e556af3aea2c70471eca13281377
            (2026-07-28, "schemas: MPCC event contract v0.1 — conversation + trading
            event family")
    sha256  7d18865d1a435f8a2e78977ef51f865b842c810f4648faa8755b506fe8b13d55
Re-vendor by copying the file from sourceos-spec and updating this block. The sha256 is
asserted at import: a drifted or hand-edited copy fails LOUDLY at startup, never
silently at emit time — the emitter's whole claim is "what enters the log conforms to
the estate contract", so the contract itself must be tamper-evident.

MarketDataEvent is a profile of the ConversationEvent envelope (same identity /
causality / governance vocabulary: id URN, type, specVersion, actorRef, workspaceRef,
branchRef, wallTime, logicalTime, provenanceLinks, policyLabels, riskLabels). Required
here: id, type, specVersion, wallTime, instrumentRef, venueRef, eventKind, rawPayload,
canonicalPayload — with additionalProperties: false, so the validator rejects both
missing fields AND invented ones.

Fail-closed startup: startup_check() re-hashes the vendored bytes, checks the schema is
itself a valid Draft 2020-12 schema, and validates one probe event built from a probe
tick — so a generator↔contract drift kills the process at boot, before a single
non-conformant object can reach the log.
"""
from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from .generator import Tick

SCHEMA_SHA256 = "7d18865d1a435f8a2e78977ef51f865b842c810f4648faa8755b506fe8b13d55"
SPEC_VERSION = "0.1.0"                       # const in the schema — pinned, not guessed
URN_PREFIX = "urn:srcos:market-data-event:"

# Fixed envelope identity for this producer (free-form refs are permitted in v0.1).
ACTOR_REF = "urn:srcos:agent:market-replay"
WORKSPACE_REF = "socioprophet"
BRANCH_REF = "main"
VENUE_REF = "SYNTH"                          # synthetic venue — clearly not a real MIC
FEED_REF = "market-replay/synthetic-walk"
NORMALIZATION_REGIME = "market-replay/synthetic-walk@v1"

_SCHEMA_BYTES = (resources.files("market_replay") / "schemas" / "MarketDataEvent.json").read_bytes()
_actual = hashlib.sha256(_SCHEMA_BYTES).hexdigest()
if _actual != SCHEMA_SHA256:  # tamper-evident vendoring — see module docstring
    raise RuntimeError(
        f"vendored MarketDataEvent.json drifted: sha256 {_actual} != pinned {SCHEMA_SHA256}; "
        "re-vendor from sourceos-spec and update contract.py provenance")

SCHEMA: dict[str, Any] = json.loads(_SCHEMA_BYTES)
VALIDATOR = Draft202012Validator(SCHEMA)

# URN local-id charset per the schema's id pattern: [A-Za-z0-9._~-]. Symbols like
# "SP:AAA" carry a colon, so the local id sanitizes it ("SP-AAA") while the event's
# instrumentRef keeps the raw symbol. One local id serves BOTH the URN and the graph
# node id, so node ↔ event identity is 1:1 by construction.
_URN_UNSAFE = re.compile(r"[^A-Za-z0-9._~-]")


def local_id(symbol: str, seq: int) -> str:
    return f"mde-{_URN_UNSAFE.sub('-', symbol)}-{seq:06d}"


def build_event(tick: Tick, wall_time: str) -> dict[str, Any]:
    """One synthetic trade tick → one MarketDataEvent-conformant object.

    rawPayload is the generator's output verbatim ("as received, before any
    normalization"); canonicalPayload declares its normalization regime, as the
    schema's invariant demands. qualityFlags carries "synthetic" — the schema's own
    example flag — so no consumer can mistake replay data for a real feed.
    """
    return {
        "id": URN_PREFIX + local_id(tick.symbol, tick.seq),
        "type": "MarketDataEvent",
        "specVersion": SPEC_VERSION,
        "actorRef": ACTOR_REF,
        "workspaceRef": WORKSPACE_REF,
        "branchRef": BRANCH_REF,
        "wallTime": wall_time,
        "logicalTime": tick.seq,
        "instrumentRef": tick.symbol,
        "venueRef": VENUE_REF,
        "eventKind": "trade",
        "sequenceRef": tick.seq,
        "feedRef": FEED_REF,
        "rawPayload": {"symbol": tick.symbol, "seq": tick.seq,
                       "price": tick.price, "volume": tick.volume},
        "canonicalPayload": {"normalizationRegime": NORMALIZATION_REGIME,
                             "instrument": tick.symbol, "price": tick.price,
                             "size": tick.volume, "side": "synthetic"},
        "qualityFlags": ["synthetic"],
        "policyLabels": ["synthetic-data"],
    }


def validate_event(event: dict[str, Any]) -> None:
    """Raises jsonschema.ValidationError on any non-conformance (fail-closed gate)."""
    VALIDATOR.validate(event)


def flatten(event: dict[str, Any], ingest_time: str) -> dict[str, Any]:
    """The graph-node property projection the materializer carries to ClickHouse:
    flat scalars for querying, PLUS the full validated event as canonical JSON — so
    the log carries the spec-conformant OBJECT, not just a lossy projection."""
    return {
        "eventId": event["id"],
        "schemaVersion": event["specVersion"],
        "eventKind": event["eventKind"],
        "symbol": event["instrumentRef"],
        "venue": event["venueRef"],
        "price": event["canonicalPayload"]["price"],
        "volume": event["canonicalPayload"]["size"],
        "seq": event["sequenceRef"],
        "eventTime": event["wallTime"],
        "ingestTime": ingest_time,
        "feed": event["feedRef"],
        "actor": event["actorRef"],
        "synthetic": True,
        "event": json.dumps(event, sort_keys=True, ensure_ascii=False),
    }


def startup_check(probe_tick: Tick, wall_time: str) -> None:
    """Boot-time fail-closed gate: schema is valid 2020-12 AND a probe event built by
    THIS code validates against it. Any drift dies here, before the first emit."""
    Draft202012Validator.check_schema(SCHEMA)
    validate_event(build_event(probe_tick, wall_time))


__all__ = ["SCHEMA", "SCHEMA_SHA256", "SPEC_VERSION", "build_event", "validate_event",
           "flatten", "local_id", "startup_check"]
