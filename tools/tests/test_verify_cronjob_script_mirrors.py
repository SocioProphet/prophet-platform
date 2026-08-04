"""Prove INV-DEP-14 (the CronJob-script no-drift gate) both ways, offline.

A gate that has only ever passed proves nothing. `verify_cronjob_script_mirrors.py` exists
because a CronJob mounts its script from a ConfigMap generated from a COPY of the canonical
tool under tools/ — two copies is the declared-not-enforced trap, where the base copy silently
drifts and the cluster runs stale code while CI proves the fresh one. So this drives the pure
`mirror_problems` seam under tmp_path through every outcome:

  * identical bytes                 => no problem (a clean mirror must pass);
  * drifted bytes (mismatch)        => DRIFT reported (the stale-code trap this gate closes);
  * absent mirror                   => "mirror missing" reported (copy never made);
  * absent canonical                => "canonical missing" reported (source deleted, mirror orphaned).

The final case runs the gate against the REAL repo pairs this PR ships, so the shipped
ConfigMap copies are proven byte-identical to their tools/ source at merge time.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_cronjob_script_mirrors.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("verify_cronjob_script_mirrors", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _pair(root: Path, canonical_bytes: bytes | None, mirror_bytes: bytes | None) -> list[str]:
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "base").mkdir(parents=True, exist_ok=True)
    if canonical_bytes is not None:
        (root / "tools" / "s.py").write_bytes(canonical_bytes)
    if mirror_bytes is not None:
        (root / "base" / "s.py").write_bytes(mirror_bytes)
    return MOD.mirror_problems(root, [("tools/s.py", "base/s.py")])


def test_identical_mirror_passes(tmp_path):
    assert _pair(tmp_path, b"print('x')\n", b"print('x')\n") == []


def test_drift_is_a_mismatch(tmp_path):
    problems = _pair(tmp_path, b"print('fresh')\n", b"print('stale')\n")
    assert any("DRIFT" in p for p in problems), problems


def test_absent_mirror_is_missing(tmp_path):
    problems = _pair(tmp_path, b"print('x')\n", None)
    assert any("mirror missing" in p for p in problems), problems


def test_absent_canonical_fails(tmp_path):
    problems = _pair(tmp_path, None, b"print('x')\n")
    assert any("canonical missing" in p for p in problems), problems


def test_shipped_pairs_are_in_sync():
    # The canonical guarantee this PR ships: the real ConfigMap copies match their tools/ source.
    assert MOD.mirror_problems(MOD.ROOT, MOD.MIRRORS) == []
