"""Import bridge for the hyphenated `services/wopi-host` source tree."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_HYPHENATED_DIR = _PACKAGE_DIR.parent / "wopi-host"

__path__ = [str(_HYPHENATED_DIR)]
