from __future__ import annotations

from zone_router.resolver import resolve_topic


def test_resolve_topic_returns_expected_format() -> None:
    result = resolve_topic("zone://edge", "carrier.ingested")
    assert result == "zone.edge.carrier.ingested.v1"


def test_resolve_topic_strips_zone_prefix() -> None:
    result = resolve_topic("zone://cloud", "carrier.ingested")
    assert result.startswith("zone.cloud.")


def test_resolve_topic_normalizes_slashes_in_event_type() -> None:
    result = resolve_topic("zone://edge", "carrier/ingested")
    assert "/" not in result


def test_resolve_topic_normalizes_underscores_in_event_type() -> None:
    result = resolve_topic("zone://edge", "carrier_ingested")
    assert "_" not in result


def test_resolve_topic_defaults_zone_when_empty() -> None:
    result = resolve_topic("", "carrier.ingested")
    assert result.startswith("zone.edge.")


def test_resolve_topic_defaults_event_type_when_none() -> None:
    result = resolve_topic("zone://edge", None)
    assert result == "zone.edge.unknown.v1"
