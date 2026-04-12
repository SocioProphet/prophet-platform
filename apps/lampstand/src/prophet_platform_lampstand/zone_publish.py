from __future__ import annotations


def build_zone_publication_request(*, carrier_ref, event_path, receipt_path, catalog_path, zone_ref="zone://edge", topic_ref=None):
    request = {
        "version": "0.1",
        "carrier_ref": carrier_ref,
        "zone_ref": zone_ref,
        "event_ref": event_path,
        "receipt_ref": receipt_path,
        "catalog_ref": catalog_path,
    }
    if topic_ref:
        request["topic_ref"] = topic_ref
    return request
