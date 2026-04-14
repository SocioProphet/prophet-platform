from __future__ import annotations

# Compatibility wrapper. The canonical runtime entrypoint now lives in app.main.
from .main import app

__all__ = ["app"]
