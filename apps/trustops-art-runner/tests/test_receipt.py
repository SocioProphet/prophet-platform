from pathlib import Path

import pytest

from trustops_art_runner.receipt import TrustOpsRunnerError, build_art_smoke_receipt


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "functional-service.demo.json"


def test_build_art_smoke_receipt_shape():
    receipt = build_art_smoke_receipt(
        manifest_path=FIXTURE,
        created_at="2026-05-05T00:00:00Z",
        source_commit="abc123",
        output_ref="artifact://trustops/art-smoke/test.json",
    )

    assert receipt["schemaVersion"] == "trustops-receipt.v1"
    assert receipt["receiptType"] == "robustness"
    assert receipt["subject"]["kind"] == "functional-service"
    assert receipt["subject"]["id"] == "demo-classifier"
    assert receipt["runner"]["provider"] == "art"
    assert receipt["inputs"]["rawDataExported"] is False
    assert receipt["evaluation"]["profile"] == "art-smoke"
    assert receipt["policy"]["decision"] == "allow"
    assert receipt["result"]["status"] == "pass"
    assert receipt["provenance"]["receiptDigest"].startswith("sha256:")


def test_art_smoke_receipt_has_required_actions():
    receipt = build_art_smoke_receipt(
        manifest_path=FIXTURE,
        created_at="2026-05-05T00:00:00Z",
    )
    actions = {(item["target"], item["action"]) for item in receipt["actions"]}

    assert ("model-governance-ledger", "record") in actions
    assert ("guardrail-fabric", "allow") in actions


def test_unsupported_profile_fails_fast():
    with pytest.raises(TrustOpsRunnerError, match="unsupported profile"):
        build_art_smoke_receipt(manifest_path=FIXTURE, profile="full-art")
