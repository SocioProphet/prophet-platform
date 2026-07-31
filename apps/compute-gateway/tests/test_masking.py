"""Read-path masking PDP tests (compute_gateway.masking)."""
from __future__ import annotations

import json

from compute_gateway import masking
from compute_gateway.contract import ComputeOutput


def _graph_output():
    return ComputeOutput(type="graph", data={
        "nodes": [
            {"id": "n1", "properties": {"mrn": "MRN-12345", "ssn": "111-22-3333", "domain": "patient"}},
            {"id": "n2", "properties": {"mrn": "MRN-99999", "ssn": "444-55-6666", "domain": "patient"}},
        ],
        "count": 2,
    })


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("GATEWAY_MASKING_POLICY", raising=False)
    outs = [_graph_output()]
    result = masking.apply(outs, kind="graph-query", project="p", actor="user", entitlement=None)
    assert result is outs  # exact passthrough, same object
    assert result[0].data["nodes"][0]["properties"]["mrn"] == "MRN-12345"


def test_field_masking_and_sealed_decision(monkeypatch):
    policy = {"policy_version": "test-v1",
              "mask_fields": {"mrn": "hmac_pseudonym", "ssn": "redact"}}
    monkeypatch.setenv("GATEWAY_MASKING_POLICY", json.dumps(policy))
    result = masking.apply([_graph_output()], kind="graph-query", project="p", actor="user", entitlement=None)
    node = result[0].data["nodes"][0]["properties"]
    assert node["mrn"].startswith("tok_"), node["mrn"]
    assert node["ssn"] == "[REDACTED]"
    assert result[0].data["nodes"][0]["properties"]["mrn"] != "MRN-12345"
    dec = result[-1]
    assert dec.type == "masking-decision"
    assert dec.data["verdict"] == "allow_masked"
    assert dec.data["schema_version"] == "identity-prime.masking-decision.v1"
    assert dec.data["decision_id"].startswith("md_")
    paths = {t["field_path"] for t in dec.data["applied_transforms"]}
    assert "properties.mrn" in paths and "properties.ssn" in paths


def test_forbidden_mixture_denies_and_withholds(monkeypatch):
    policy = {"policy_version": "test-v1",
              "forbidden_mixtures": [["patient", "ad_tech"]],
              "requesting_realm_topics": {"adbot": "ad_tech"},
              "record_topic_fields": ["domain"],
              "mask_fields": {"mrn": "redact"}}
    monkeypatch.setenv("GATEWAY_MASKING_POLICY", json.dumps(policy))
    result = masking.apply([_graph_output()], kind="graph-query", project="p", actor="adbot-7", entitlement=None)
    assert len(result) == 1 and result[0].type == "masking-decision"
    assert result[0].data["verdict"] == "deny"
    assert result[0].data["forbidden_mixture"] == ["ad_tech", "patient"]


def test_pseudonym_is_deterministic(monkeypatch):
    monkeypatch.setenv("GATEWAY_MASKING_KEY", "k")
    a = masking._transform("MRN-1", "hmac_pseudonym")
    b = masking._transform("MRN-1", "hmac_pseudonym")
    c = masking._transform("MRN-2", "hmac_pseudonym")
    assert a == b and a != c and a.startswith("tok_")


def test_unknown_scheme_fails_closed():
    assert masking._transform("secret", "bogus-scheme") == "[REDACTED]"


def test_invalid_policy_disables_off(monkeypatch):
    monkeypatch.setenv("GATEWAY_MASKING_POLICY", "{not json")
    outs = [_graph_output()]
    assert masking.apply(outs, kind="graph-query", project="p", actor="u", entitlement=None) is outs
