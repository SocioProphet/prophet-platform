"""The ref-gate must DISCRIMINATE: a dangling $ref fails, a resolving one passes, and data files
are not mistaken for schemas. Tested on synthetic inputs so it never depends on the live tree."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import validate_schema_references as v  # noqa: E402


def test_is_schema_discriminates_data_from_schema():
    assert v._is_schema({"$id": "x", "type": "object"}) is True
    assert v._is_schema({"$schema": "..."}) is True
    assert v._is_schema({"foo": "bar"}) is False           # an example / data file
    assert v._is_schema(["not", "an", "object"]) is False


def test_resolve_pointer_walks_defs_and_arrays():
    doc = {"$defs": {"a": {"type": "string"}}, "allOf": [{"x": 1}]}
    assert v.resolve_pointer(doc, "/$defs/a") is True
    assert v.resolve_pointer(doc, "/allOf/0") is True
    assert v.resolve_pointer(doc, "/$defs/missing") is False
    assert v.resolve_pointer(doc, "/allOf/9") is False


def test_resolve_ref_by_id_name_and_dangling():
    good = {"$id": "https://x/Good.json", "$defs": {"a": {}}}
    p = Path("/tmp/x.json").resolve()
    kw = dict(by_path={p: good}, by_name={"Good.json": good}, by_id={good["$id"]: good})
    assert v.resolve_ref("Good.json", from_path=p, **kw)[0] is True
    assert v.resolve_ref(good["$id"], from_path=p, **kw)[0] is True
    assert v.resolve_ref("Nope.json", from_path=p, **kw)[0] is False


def test_end_to_end_catches_a_dangling_ref(tmp_path, monkeypatch):
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "Good.json").write_text('{"$id":"g","$defs":{"a":{"type":"string"}}}')
    (tmp_path / "contracts" / "Bad.json").write_text('{"$id":"b","properties":{"x":{"$ref":"#/$defs/nope"}}}')
    (tmp_path / "contracts" / "example.json").write_text('{"just":"data"}')  # skipped, not a schema
    monkeypatch.setattr(v, "ROOT", tmp_path)
    findings, n, refs = v.check_all(tmp_path)
    assert n == 2  # only the two schemas, not the data file
    assert any("Bad.json" in name for name, _ in findings)


def test_self_test_exit_code_is_zero(capsys):
    assert v.main(["--self-test"]) == 0
