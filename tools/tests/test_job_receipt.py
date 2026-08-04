"""The receipt helper exists to catch the three silent ways a scheduled job fails you:
it stopped running (stale), it ran and failed (rc!=0), or it never ran (missing). Each is pinned."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import job_receipt as jr  # noqa: E402


def test_roundtrip_fresh_success_is_clean(tmp_path):
    jr.write_receipt("backup", 0, directory=tmp_path)
    assert jr.verify_receipts(tmp_path, max_age_s=3600) == []


def test_stale_receipt_flagged(tmp_path):
    jr.write_receipt("backup", 0, directory=tmp_path, ts=time.time() - 99999)
    out = jr.verify_receipts(tmp_path, max_age_s=3600)
    assert any("stale" in p for p in out)


def test_failed_receipt_flagged(tmp_path):
    jr.write_receipt("backup", 2, directory=tmp_path)
    assert any("rc=2" in p for p in jr.verify_receipts(tmp_path, max_age_s=3600))


def test_missing_expected_receipt_flagged(tmp_path):
    out = jr.verify_receipts(tmp_path, max_age_s=3600, expect=["nightly-backup"])
    assert any("missing" in p for p in out)


def test_unreadable_receipt_flagged(tmp_path):
    (tmp_path / "junk.json").write_text("{not json")
    assert any("unreadable" in p for p in jr.verify_receipts(tmp_path, max_age_s=3600))


def test_written_shape_matches_alerter_receipts_contract(tmp_path):
    import json
    p = jr.write_receipt("x", 0, directory=tmp_path)
    d = json.loads(p.read_text())
    assert set(d) == {"job", "ts", "rc"} and d["job"] == "x" and d["rc"] == 0


def test_cli_write_then_verify(tmp_path):
    assert jr.main(["write", "job-a", "0", "--dir", str(tmp_path)]) == 0
    assert jr.main(["verify", "--dir", str(tmp_path), "--max-age", "3600"]) == 0
    jr.write_receipt("job-b", 1, directory=tmp_path)
    assert jr.main(["verify", "--dir", str(tmp_path), "--max-age", "3600"]) == 1
