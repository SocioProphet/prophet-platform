from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "emit_reasoning_failure_receipt.py"

spec = importlib.util.spec_from_file_location("emit_reasoning_failure_receipt", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)

CASE_PATH = ROOT / "examples" / "reasoning-failure" / "exact-string-case.json"
SUITE_PATH = ROOT / "examples" / "reasoning-failure" / "exactness-perturbation-suite.json"
SCHEMA_PATH = ROOT / "schemas" / "runtime" / "reasoning-failure-receipt-v0.1.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_emit_exactness_failure_receipt() -> None:
    receipt = module.emit_receipt(load(CASE_PATH), load(SUITE_PATH))

    assert receipt["kind"] == "ReasoningFailureReceipt"
    assert receipt["version"] == "0.1"
    assert receipt["caseId"] == "reasoning-failure.exact-string.synthetic.v0"
    assert receipt["suiteId"] == "perturbation-suite.exactness.synthetic.v0"
    assert receipt["runner"]["deterministic"] is True
    assert receipt["privacyBoundary"] == "synthetic-only"
    assert receipt["verifierFamily"] == "deterministic"
    assert receipt["decision"] == "failed"
    assert receipt["riskAction"] == "require-tool-verification"
    assert receipt["invariantResults"][0]["passed"] is False
    assert receipt["invariantResults"][0]["expected"] == "sourceos-syncd.release-set.v0.1"
    assert receipt["invariantResults"][0]["observed"] == "sourceos_syncd.release_set.v0.1"
    assert "SocioProphet/guardrail-fabric" in receipt["nextConsumers"]


def test_emit_exactness_pass_receipt_when_strings_match() -> None:
    case = load(CASE_PATH)
    suite = load(SUITE_PATH)
    case["observedString"] = case["protectedString"]

    receipt = module.emit_receipt(case, suite)

    assert receipt["decision"] == "passed"
    assert receipt["riskAction"] == "record-only"
    assert receipt["invariantResults"][0]["passed"] is True


def test_emit_refuses_suite_case_mismatch() -> None:
    case = load(CASE_PATH)
    suite = load(SUITE_PATH)
    suite["targetCaseId"] = "reasoning-failure.other.synthetic.v0"

    with pytest.raises(module.ReasoningFailureRunnerError, match="suite.targetCaseId"):
        module.emit_receipt(case, suite)


def test_emit_refuses_llm_judge_only_case() -> None:
    case = load(CASE_PATH)
    suite = load(SUITE_PATH)
    case["verifier"]["llmJudgeOnly"] = True

    with pytest.raises(module.ReasoningFailureRunnerError, match="LLM-judge-only"):
        module.emit_receipt(case, suite)


def test_receipt_schema_required_fields_are_present() -> None:
    schema = load(SCHEMA_PATH)
    receipt = module.emit_receipt(load(CASE_PATH), load(SUITE_PATH))

    for required in schema["required"]:
        assert required in receipt

    assert schema["title"] == "ReasoningFailureReceipt"
