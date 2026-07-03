from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "emit_autonomy_admission_receipt.py"
VALIDATOR = REPO_ROOT / "tools" / "validate_autonomy_admission_receipt.py"
CHANNEL_GATE = REPO_ROOT / "contracts" / "channel-governance" / "runtime-gate.candidate-memory.example.json"


def _emit(tmp_path: Path, *args: str) -> dict:
    out = tmp_path / "receipt.json"
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--out", str(out), *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def _validates(receipt_path: Path) -> bool:
    proc = subprocess.run([sys.executable, str(VALIDATOR), str(receipt_path)], capture_output=True, text=True)
    return proc.returncode == 0


def test_emit_admit_l4_with_evidence(tmp_path: Path):
    out = tmp_path / "r.json"
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--out", str(out),
         "--role", "conductor", "--level", "L4",
         "--evidence", "conductor_response_envelope",
         "--evidence-refs", "evidence://envelope/turn-1",
         "--subject-ref", "agent://choir/conductor/run-1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["decision"] == "admit"
    assert receipt["granted_level"] == "L4"
    assert receipt["hash"].startswith("sha256:")
    # The emitted receipt must pass the contract validator.
    assert _validates(out)


def test_emit_demotes_when_evidence_absent(tmp_path: Path):
    receipt = _emit(
        tmp_path, "--role", "coding", "--level", "L3",
        "--evidence", "test_result_or_review_receipt",  # supports L2, not L3
        "--evidence-refs", "evidence://eval-fabric/replay/job-2/passed",
        "--subject-ref", "agent://choir/coding/run-2",
    )
    assert receipt["decision"] == "demote"
    assert receipt["granted_level"] == "L2"


def test_emit_binds_to_channel_gate(tmp_path: Path):
    receipt = _emit(
        tmp_path, "--role", "conductor", "--level", "L4",
        "--evidence", "conductor_response_envelope",
        "--channel-gate", str(CHANNEL_GATE),
    )
    # subject + envelope + policy refs pulled from the channel-governed gate
    assert receipt["subject_ref"] == "platform-operation:conversation-ingest-001"
    assert receipt["envelope_ref"].startswith("channel-runtime-gate:")
    assert "prophet-mesh:specs/ai-driven-development.yaml" in receipt["policy_refs"]


def test_hash_is_deterministic_over_content(tmp_path: Path):
    common = ["--role", "research", "--level", "L3", "--evidence", "evidence_dossier",
              "--evidence-refs", "evidence://dossier/x",
              "--subject-ref", "s://x", "--receipt-id", "fixed-id", "--out", str(tmp_path / "a.json")]
    p1 = subprocess.run([sys.executable, str(TOOL), *common], capture_output=True, text=True)
    assert p1.returncode == 0, p1.stderr
    r1 = json.loads((tmp_path / "a.json").read_text())
    # recompute hash by stripping it and hashing canonically must match
    import hashlib
    body = {k: v for k, v in r1.items() if k != "hash"}
    recomputed = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert recomputed == r1["hash"]
