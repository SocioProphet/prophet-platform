"""Prove COST GUARD 1 (change-detection skip) both ways.

A gate that has only ever passed proves nothing — so this feeds the tool a positive (source
unchanged => SKIP, exit 0) AND a negative (source changed => BUILD, exit 10), plus the
fail-closed error path (a missing declared source path must ERROR, never hash a partial tree).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "compute_source_content_digest.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("compute_source_content_digest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _mklock(path: Path, content_digest: str) -> Path:
    path.write_text(json.dumps({"source_content_digest": content_digest}), encoding="utf-8")
    return path


def test_digest_is_deterministic_and_content_only(tmp_path) -> None:
    src = tmp_path / "svc"
    src.mkdir()
    (src / "a.py").write_text("print(1)\n", encoding="utf-8")
    (src / "b.py").write_text("print(2)\n", encoding="utf-8")
    d1 = MOD.compute_digest([src], root=tmp_path)
    d2 = MOD.compute_digest([src], root=tmp_path)
    assert d1 == d2, "same tree must hash identically"
    assert d1.startswith("sha256:") and len(d1) == 7 + 64
    # A content change must change the digest.
    (src / "b.py").write_text("print(3)\n", encoding="utf-8")
    assert MOD.compute_digest([src], root=tmp_path) != d1


def test_decide_skip_when_unchanged(tmp_path, monkeypatch, capsys) -> None:
    src = tmp_path / "svc"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    digest = MOD.compute_digest([src], root=tmp_path)
    lock = _mklock(tmp_path / "lock.json", digest)
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["decide", "--path", str(src), "--lock", str(lock)])
    assert rc == 0, "unchanged source must SKIP (exit 0)"
    assert "SKIP" in capsys.readouterr().out


def test_decide_build_when_changed(tmp_path, monkeypatch, capsys) -> None:
    src = tmp_path / "svc"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    lock = _mklock(tmp_path / "lock.json", "sha256:" + ("0" * 64))  # a different, stale digest
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["decide", "--path", str(src), "--lock", str(lock)])
    assert rc == 10, "changed source must BUILD (exit 10)"
    assert "BUILD" in capsys.readouterr().out


def test_decide_build_when_lock_missing_and_allowed(tmp_path, monkeypatch) -> None:
    src = tmp_path / "svc"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = MOD.main(["decide", "--path", str(src), "--lock", str(tmp_path / "nope.json"),
                   "--allow-missing"])
    assert rc == 10, "first build of a new component (no lock) must BUILD"


def test_missing_source_path_is_fail_closed(tmp_path) -> None:
    try:
        MOD.compute_digest([tmp_path / "does-not-exist"], root=tmp_path)
    except SystemExit as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("a missing source path must ERROR, not hash a partial tree")
