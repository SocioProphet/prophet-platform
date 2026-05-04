from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from jsonschema import Draft202012Validator


def load_module(repo_root: Path) -> ModuleType:
    module_path = repo_root / "apps" / "identity-prime" / "src" / "identity_prime" / "proof_ingress.py"
    spec = importlib.util.spec_from_file_location("identity_prime_proof_ingress", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_emit_proof_ingress_record_validates_against_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    module = load_module(repo_root)
    schema = load_json(repo_root / "contracts" / "identity" / "IdentityProofIngressRecord.v0.1.json")
    record = module.emit_proof_ingress_record(
        proof_source="enterprise_oidc",
        tenant_id="tenant_acme",
        result="accepted",
        subject_id="subj_01HUMAN123",
        issuer_ref="issuer_acme_oidc",
        upstream_subject="00u-example-subject",
        assurance_context={"level": "aal2_phishing_resistant_target"},
        evidence_refs=["evidence_proof_accepted_0001"],
        correlation_id="corr_identity_ingress_0001",
        proof_record_id="proof_enterprise_oidc_0001",
        received_at="2026-05-04T19:50:00Z",
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(record)
    assert record["proof_record_id"] == "proof_enterprise_oidc_0001"
    assert record["proof_source"] == "enterprise_oidc"
    assert record["result"] == "accepted"


def test_emit_proof_ingress_record_rejects_invalid_source() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    module = load_module(repo_root)

    try:
        module.emit_proof_ingress_record(
            proof_source="unknown_source",
            tenant_id="tenant_acme",
            result="accepted",
        )
    except ValueError as exc:
        assert "unsupported proof_source" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported proof_source")


def test_emit_proof_ingress_record_requires_tenant_id() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    module = load_module(repo_root)

    try:
        module.emit_proof_ingress_record(
            proof_source="enterprise_oidc",
            tenant_id="",
            result="accepted",
        )
    except ValueError as exc:
        assert "tenant_id is required" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing tenant_id")
