import json
import subprocess
import sys
from pathlib import Path


POLICY_FABRIC_DECISION_CONTRACT = "schema://policy-fabric/contracts/prophet_operations_action_decision_v1.schema.json"
DEFAULT_OPERATIONS_POLICY_REF = "policy://operations/default-action-gates/v1"


def test_normalize_prophet_operations_evidence(tmp_path: Path):
    raw = {
        "source": {"system": "local-demo", "emitter": "unit-test"},
        "observed_at": "2026-04-25T18:00:00Z",
        "signals": [
            {
                "subject": {"id": "svc-api", "type": "service", "name": "api"},
                "signal": {"name": "error_rate", "type": "metric", "value": 0.12, "unit": "ratio", "severity": "warn"},
            },
            {
                "subject": {"id": "worker-1", "type": "workload", "name": "worker"},
                "signal": {"name": "restart_loop", "type": "event", "value": True, "severity": "error"},
            },
        ],
        "topology": {
            "scope": {"environment": "test"},
            "nodes": [
                {"id": "svc-api", "type": "service", "name": "api"},
                {"id": "worker-1", "type": "workload", "name": "worker"},
            ],
            "edges": [{"from": "svc-api", "to": "worker-1", "type": "depends_on"}],
        },
    }
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "bundle.json"
    input_path.write_text(json.dumps(raw), encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "normalize_prophet_operations_evidence.py"
    subprocess.run([sys.executable, str(script), str(input_path), "--output", str(output_path)], check=True)

    bundle = json.loads(output_path.read_text(encoding="utf-8"))
    assert bundle["kind"] == "ProphetOperationsEvidenceBundle"
    assert len(bundle["signals"]) == 2
    assert bundle["topology"]["kind"] == "ProphetRuntimeTopologyEvidence"
    assert {item["health"]["state"] for item in bundle["health_assessments"]} == {"degraded", "unhealthy"}
    assert len(bundle["recommendations"]) == 2
    assert all(item["policy_gate"]["required"] for item in bundle["recommendations"])
    assert {item["action"]["type"] for item in bundle["recommendations"]} == {"investigate", "isolate"}

    for recommendation in bundle["recommendations"]:
        gate = recommendation["policy_gate"]
        assert gate["policy_ref"] == DEFAULT_OPERATIONS_POLICY_REF
        assert gate["decision_contract_ref"] == POLICY_FABRIC_DECISION_CONTRACT
        assert gate["decision_ref"].startswith("policy-fabric://prophet-operations-action-decision/v1/oprec-")
        assert gate["decision"] == "pending"

    assert len(bundle["evidence_links"]) == len(bundle["recommendations"])
    linked_recommendations = {link["recommendation_ref"] for link in bundle["evidence_links"]}
    assert linked_recommendations == {item["recommendation_id"] for item in bundle["recommendations"]}
    assert all(link["relationship"] == "requires_policy_decision" for link in bundle["evidence_links"])
    assert all(link["contract_ref"] == POLICY_FABRIC_DECISION_CONTRACT for link in bundle["evidence_links"])
    assert all(link["to_ref"].startswith("policy-fabric://prophet-operations-action-decision/v1/oprec-") for link in bundle["evidence_links"])
