from __future__ import annotations

import os
from typing import Any

import httpx


def _base_url() -> str:
    return os.environ.get("EVIDENCE_RECEIPTS_BASE_URL", "http://localhost:8090").rstrip("/")


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(f"{_base_url()}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


def get_services() -> list[str]:
    return _get("/v1/services").get("services", [])


def get_recent_receipts(service: str, limit: int = 20) -> list[dict[str, Any]]:
    return _get("/v1/receipts/recent", params={"service": service, "limit": limit}).get("items", [])


def get_bundle(service: str, correlation_id: str) -> dict[str, Any]:
    return _get(f"/v1/receipts/{service}/{correlation_id}")


def get_recent_catalog(service: str, limit: int = 20) -> list[dict[str, Any]]:
    return _get("/v1/catalog/recent", params={"service": service, "limit": limit}).get("items", [])
