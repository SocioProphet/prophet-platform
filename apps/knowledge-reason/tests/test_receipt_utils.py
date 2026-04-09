from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "apps" / "knowledge-reason" / "service" / "receipt_utils.py"
SPEC = importlib.util.spec_from_file_location("receipt_utils", MODULE_PATH)
assert SPEC and SPEC.loader
receipt_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receipt_utils)


def test_canonical_json_is_order_stable():
    a = {"b": 1, "a": {"y": 2, "x": 1}}
    b = {"a": {"x": 1, "y": 2}, "b": 1}
    assert receipt_utils.canonical_json(a) == receipt_utils.canonical_json(b)


def test_sha256_hex_is_stable_for_equivalent_payloads():
    a = {"message": "שלום", "n": 1}
    b = {"n": 1, "message": "שלום"}
    assert receipt_utils.sha256_hex(a) == receipt_utils.sha256_hex(b)
