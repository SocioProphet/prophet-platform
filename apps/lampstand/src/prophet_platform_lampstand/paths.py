from __future__ import annotations

import os
from pathlib import Path


def _home_fallback(suffix: str) -> Path:
    return Path.home() / suffix


def data_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_DATA_HOME"):
        return Path(v)
    return _home_fallback(".local/share")


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return _home_fallback(".local/state")


def runtime_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_RUNTIME_HOME"):
        return Path(v)
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        return Path(xdg_runtime)
    return _home_fallback(".local/run")


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def payloads_root(service: str = "lampstand") -> Path:
    return platform_state_root() / "payloads" / service


def events_root(service: str = "lampstand") -> Path:
    return platform_state_root() / "events" / service


def receipts_root(service: str = "lampstand") -> Path:
    return platform_state_root() / "receipts" / service


def catalog_root(service: str = "lampstand") -> Path:
    return platform_state_root() / "catalog" / service


def ensure_service_dirs(service: str = "lampstand") -> None:
    for p in [payloads_root(service), events_root(service), receipts_root(service), catalog_root(service)]:
        p.mkdir(parents=True, exist_ok=True)
