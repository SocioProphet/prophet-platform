"""Test bootstrap.

Same `sys.path.insert` convention as apps/ie-engine/tests and apps/dashboard-bff — no
package install step, so the suite runs from a clean checkout.

Note for anyone extending this with importlib-based module loading (as dashboard-bff's
`_load_module` does): on Python 3.12 a module loaded via importlib must be registered in
`sys.modules` BEFORE `exec_module`, or every `@dataclass` it defines fails to resolve
`cls.__module__` and raises AttributeError on None. This package defines many dataclasses;
plain imports are used here precisely to stay clear of that.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
