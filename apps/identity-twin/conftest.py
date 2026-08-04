"""Make the `app` package importable under bare `pytest` (not only `python -m pytest`) by putting
this app's root on sys.path. The vendored `procyber` tree is added in turn by app/__init__.py."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
