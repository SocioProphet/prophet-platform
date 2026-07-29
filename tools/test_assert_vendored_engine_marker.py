"""Coverage for tools/assert_vendored_engine_marker.py.

Pins the load-bearing property of the re-vendor discipline: the assertion reads the
packed dist (not package.json) and a substring is not a marker. The real vendored
0.4.45 tarball must pass on the full PROP_NS assignment; a bundle that carries only the
decoy substring `prop:` must fail — that decoy is present in 0.4.40 too, which is the
whole reason a substring proves nothing.
"""
from __future__ import annotations

import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "assert_vendored_engine_marker.py"
REAL_045 = ROOT / "apps" / "hellgraph-service" / "vendor" / "socioprophet-hellgraph-0.4.45.tgz"
MARKER = 'PROP_NS = "prop:"'


def _load():
    spec = importlib.util.spec_from_file_location("assert_vendored_engine_marker", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load()


def _tarball(path: Path, index_js: str) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        data = index_js.encode("utf-8")
        info = tarfile.TarInfo("package/ts/dist/index.js")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return path


def test_real_045_passes_on_full_marker():
    # The committed production tarball genuinely carries the marker.
    assert tool.main([str(REAL_045), "--expect", MARKER]) == 0


def test_decoy_substring_is_not_a_marker(tmp_path):
    # Carries 'prop:' (present in BOTH 0.4.40 and 0.4.45) but not the full assignment.
    t = _tarball(tmp_path / "decoy.tgz", 'const x = "prop:"; // no PROP_NS assignment here')
    assert tool.main([str(t), "--expect", MARKER]) == 1


def test_missing_dist_member_fails_loudly(tmp_path):
    empty = tmp_path / "empty.tgz"
    with tarfile.open(empty, "w:gz"):
        pass
    with pytest.raises(SystemExit):
        tool.main([str(empty), "--expect", MARKER])


def test_forbidden_marker_present_fails(tmp_path):
    t = _tarball(tmp_path / "has-old.tgz", f'{MARKER}\nconst legacyGraphLabels = true;')
    assert tool.main([str(t), "--expect", MARKER, "--forbid", "legacyGraphLabels"]) == 1


def test_expect_required():
    # A version field is not evidence — refuse to "pass" with nothing asserted.
    assert tool.main([str(REAL_045)]) == 1
