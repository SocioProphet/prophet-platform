from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring


class FeedError(ValueError):
    """Raised when feed serialization cannot satisfy the export contract."""


def private_feed_document(cell: dict[str, Any], feed_items: list[dict[str, Any]], signals: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a private feed document for a cell.

    The private feed is intentionally JSON-first because it is the canonical
    internal/export surface. RSS is derived from the same feed item records.
    """

    _require(cell, ["id", "owner_ref", "kind"])
    signals = signals or {}
    items = [_private_feed_item(item, signals.get(item.get("signal_id", ""))) for item in sorted(feed_items, key=lambda value: value.get("created_at", ""), reverse=True)]
    return {
        "feed_kind": "private",
        "cell_id": cell["id"],
        "owner_ref": cell["owner_ref"],
        "cell_kind": cell["kind"],
        "generated_at": _now(),
        "item_count": len(items),
        "items": items,
    }


def rss_feed_document(
    *,
    cell: dict[str, Any],
    feed_items: list[dict[str, Any]],
    signals: dict[str, dict[str, Any]] | None = None,
    title: str | None = None,
    link: str = "https://socioprophet.local/feeds/private",
    description: str | None = None,
) -> str:
    """Build an RSS 2.0 XML feed from private feed item records."""

    _require(cell, ["id", "owner_ref", "kind"])
    signals = signals or {}
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = title or f"Personal Intelligence Cell Feed: {cell['id']}"
    SubElement(channel, "link").text = link
    SubElement(channel, "description").text = description or "Governed private feed exported by SocioProphet Personal Intelligence Cell runtime."
    SubElement(channel, "lastBuildDate").text = _rfc822(_now())

    for feed_item in sorted(feed_items, key=lambda value: value.get("created_at", ""), reverse=True):
        signal = signals.get(feed_item.get("signal_id", ""))
        item = SubElement(channel, "item")
        title_text = feed_item.get("title") or (signal or {}).get("title") or feed_item.get("id") or "Untitled cell feed item"
        body_text = feed_item.get("body") or (signal or {}).get("summary") or ""
        SubElement(item, "title").text = title_text
        SubElement(item, "link").text = _item_link(feed_item)
        SubElement(item, "guid", {"isPermaLink": "false"}).text = feed_item.get("id") or _item_link(feed_item)
        SubElement(item, "description").text = escape(body_text)
        if feed_item.get("created_at"):
            SubElement(item, "pubDate").text = _rfc822(feed_item["created_at"])
        if feed_item.get("signal_id"):
            SubElement(item, "source").text = feed_item["signal_id"]

    return tostring(rss, encoding="unicode")


def _private_feed_item(feed_item: dict[str, Any], signal: dict[str, Any] | None) -> dict[str, Any]:
    _require(feed_item, ["id", "cell_id", "signal_id", "feed_kind", "created_at"])
    policy = feed_item.get("policy_decision") or {}
    return {
        "id": feed_item["id"],
        "cell_id": feed_item["cell_id"],
        "signal_id": feed_item["signal_id"],
        "feed_kind": feed_item["feed_kind"],
        "title": feed_item.get("title") or (signal or {}).get("title"),
        "body": feed_item.get("body") or (signal or {}).get("summary"),
        "created_at": feed_item["created_at"],
        "policy_decision": policy.get("decision"),
        "policy_ref": policy.get("policy_ref"),
        "signal": _signal_summary(signal) if signal else None,
    }


def _signal_summary(signal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not signal:
        return None
    return {
        "id": signal.get("id"),
        "source_id": signal.get("source_id"),
        "watch_id": signal.get("watch_id"),
        "title": signal.get("title"),
        "summary": signal.get("summary"),
        "extractions": signal.get("extractions", {}),
        "evidence_refs": signal.get("evidence_refs", []),
        "novelty_score": signal.get("novelty_score"),
        "relevance_score": signal.get("relevance_score"),
        "confidence_score": signal.get("confidence_score"),
        "policy_status": signal.get("policy_status"),
    }


def _item_link(feed_item: dict[str, Any]) -> str:
    safe_id = escape(str(feed_item.get("id", "feed-item"))).replace(" ", "%20")
    return f"https://socioprophet.local/feed-items/{safe_id}"


def _rfc822(value: str) -> str:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(obj: dict[str, Any], keys: list[str]) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise FeedError(f"missing required feed keys: {', '.join(missing)}")
