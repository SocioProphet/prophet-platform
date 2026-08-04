"""identity-twin FastAPI app.

Puts the pinned `third_party/` tree on sys.path so the vendored ProCybernetica twin library is
importable as `procyber.semantic.*` no matter how the app is launched (uvicorn, pytest, Docker).
The app *consumes* the vendored, hash-pinned library — never a system-installed copy — so a
drifted vendor is caught by the smoke test, not silently imported."""
from __future__ import annotations

import sys
from pathlib import Path

_VENDOR = Path(__file__).resolve().parent.parent / "third_party"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
