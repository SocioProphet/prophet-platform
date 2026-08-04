"""crystal-atlas-contract-intel app.

Puts the pinned `third_party/` tree on sys.path so the vendored ProCybernetica semantic
library is importable as `procyber.semantic.*` however the app is launched (uvicorn,
pytest, Docker). The app *consumes* the vendored, hash-pinned library — never a
system-installed copy — so a drifted vendor is caught by the freshness test rather than
silently imported. Same discipline as apps/identity-twin, deliberately.
"""
from __future__ import annotations

import sys
from pathlib import Path

_VENDOR = Path(__file__).resolve().parent.parent / "third_party"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
