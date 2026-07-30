"""Coverage for tools/assert_vendored_engine_marker.py.

Pins the load-bearing property of the re-vendor discipline: the assertion reads the
packed dist (not package.json) and a substring is not a marker. The real vendored
0.4.45 tarball must pass on the full PROP_NS assignment; a bundle that carries only the
decoy substring `prop:` must fail — that decoy is present in 0.4.40 too, which is the
whole reason a substring proves nothing.
"""
from __future__ import annotations

import importlib.util
import inspect
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
    if spec is None or spec.loader is None:
        raise AssertionError(
            f"cannot build an import spec for {TOOL} — the tool is missing or unreadable. "
            "Failing here rather than on a downstream AttributeError so the cause is the message.")
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


# ── The assertion must be shown to FIRE, not merely to exist ──────────────
#
# Everything above this line proves the tool passes on the real tarball and
# fails on hand-built toys. That is not the same claim. An assertion whose only
# negative cases are synthetic can still be blind to the real artifact — the
# toys are 60-byte files, the real dist is 395 KB of minified bundle that the OS
# classifies as `data`. So the negative case is built by mutating the REAL
# 0.4.45 tarball and re-running the tool against it.
#
# This is the whole point of the tool. A re-vendor check that cannot go red is
# a rubber stamp with a receipt attached.

MEMBER = "package/ts/dist/index.js"


def _mutate_real(dst: Path, old: bytes, new: bytes) -> Path:
    """Rebuild the real 0.4.45 tarball with one substitution in the packed dist."""
    with tarfile.open(REAL_045, "r:gz") as src, tarfile.open(dst, "w:gz") as out:
        for m in src.getmembers():
            data = src.extractfile(m).read() if m.isfile() else None
            if m.name == MEMBER:
                assert old in data, "mutation target absent — the fixture, not the tool, is wrong"
                data = data.replace(old, new)
                m.size = len(data)
            out.addfile(m, io.BytesIO(data) if data is not None else None)
    return dst


def test_real_tarball_with_the_marker_removed_goes_RED(tmp_path):
    """Break the marker in the real bundle; the decoy substring `prop:` is left
    in place, so only the full assignment distinguishes pass from fail."""
    broken = _mutate_real(tmp_path / "broken.tgz",
                          b'PROP_NS = "prop:"', b'PROP_NS_RENAMED = "prop:"')
    assert tool.main([str(broken), "--expect", MARKER]) == 1
    # And the tool is not merely rejecting any rebuilt tarball: an untouched
    # rebuild of the same bytes still passes.
    same = _mutate_real(tmp_path / "same.tgz", b'PROP_NS = "prop:"', b'PROP_NS = "prop:"')
    assert tool.main([str(same), "--expect", MARKER]) == 0


def test_real_tarball_with_one_character_changed_goes_RED(tmp_path):
    """Single-character mutation: PROP_NS -> PROP_N5. The check must be exact."""
    broken = _mutate_real(tmp_path / "onechar.tgz",
                          b'PROP_NS = "prop:"', b'PROP_N5 = "prop:"')
    assert tool.main([str(broken), "--expect", MARKER]) == 1


def test_a_substring_marker_would_NOT_have_caught_it(tmp_path):
    """The reason --expect must carry the whole assignment. Against the same
    broken bundle, the substring `prop:` passes — it is present in 0.4.40 too,
    so it discriminates nothing. This test exists to keep the marker strong:
    it fails if someone weakens --expect and assumes the tool still works."""
    broken = _mutate_real(tmp_path / "weak.tgz",
                          b'PROP_NS = "prop:"', b'PROP_NS_RENAMED = "prop:"')
    assert tool.main([str(broken), "--expect", "prop:"]) == 0
    assert tool.main([str(broken), "--expect", MARKER]) == 1


def test_the_dist_trips_binary_heuristics_but_containment_is_unaffected():
    """Pins the docstring's justification as an actual property of the artifact
    rather than a claim about some particular grep build.

    Deliberately does NOT assert what `grep` returns. Writing this test first
    with `assert grep_returncode == 1` made it fail: /usr/bin/grep finds all
    three occurrences, and the docstring's original "grep reports zero" claim
    turned out to have been measured through a broken shell shim. Asserting a
    tool-specific exit code here would either encode that false claim or make CI
    depend on which grep the runner ships.

    What IS stably true, and is what the tool relies on: the bundle carries a NUL
    byte, so it is a legitimate binary-heuristic trigger for any searcher, while
    Python containment has no such mode and answers over the bytes."""
    with tarfile.open(REAL_045, "r:gz") as t:
        raw = t.extractfile(MEMBER).read()
    assert b"\x00" in raw, (
        "the dist no longer contains a NUL byte — binary heuristics may no longer "
        "trigger, so the docstring's justification needs revisiting")
    assert raw.count(b"PROP_NS") == 3, "fixture changed; update the expected count"
    dist = tool.read_member(REAL_045, MEMBER)
    assert MARKER in dist, "Python containment must find the marker regardless"


# ── Copilot round-1: bounded, typed member reads ──────────────────────────

def test_oversized_member_is_refused_rather_than_read(tmp_path):
    """A decompression bomb must not be read into memory. Highly compressible
    zeros: tiny on disk, enormous expanded."""
    bomb = tmp_path / "bomb.tgz"
    payload = b"\0" * (tool.MAX_MEMBER_BYTES + 4096)
    with tarfile.open(bomb, "w:gz") as tar:
        info = tarfile.TarInfo(MEMBER)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    assert bomb.stat().st_size < 200_000, "fixture must be small on disk to be a bomb"
    with pytest.raises(SystemExit) as e:
        tool.main([str(bomb), "--expect", MARKER])
    assert "refusing to read" in str(e.value)


def test_non_regular_member_is_refused(tmp_path):
    """A symlink named like the dist must not be followed."""
    linky = tmp_path / "linky.tgz"
    with tarfile.open(linky, "w:gz") as tar:
        info = tarfile.TarInfo(MEMBER)
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../../etc/passwd"
        tar.addfile(info)
    with pytest.raises(SystemExit) as e:
        tool.main([str(linky), "--expect", MARKER])
    assert "not a regular file" in str(e.value)


# ── Copilot round-2 ───────────────────────────────────────────────────────

def test_a_corrupt_tarball_fails_cleanly_not_with_a_stack_trace(tmp_path):
    """Automation reads the exit code. A ReadError escaping as a traceback is a
    different failure mode from every other error path in this tool."""
    junk = tmp_path / "corrupt.tgz"
    junk.write_bytes(b"this is definitely not a gzip stream")
    with pytest.raises(SystemExit) as e:
        tool.main([str(junk), "--expect", MARKER])
    assert "not a readable gzip tarball" in str(e.value)


def test_a_directory_passed_as_a_tarball_fails_cleanly(tmp_path):
    d = tmp_path / "adir.tgz"
    d.mkdir()
    with pytest.raises(SystemExit) as e:
        tool.main([str(d), "--expect", MARKER])
    assert "not a readable gzip tarball" in str(e.value)


def test_the_tarball_digest_is_streamed_not_slurped():
    """The receipt digest must not undo read_member's bounded read one line later.
    Same digest as a whole-file hash, without holding the file in memory."""
    import hashlib
    assert tool.sha256_file(REAL_045) == hashlib.sha256(REAL_045.read_bytes()).hexdigest()
    src = inspect.getsource(tool.main)
    assert "read_bytes()" not in src, (
        "main() slurps the whole tarball to hash it — this tool runs on registry-pulled "
        "artifacts of unknown size, which is the exact case read_member() bounds")
