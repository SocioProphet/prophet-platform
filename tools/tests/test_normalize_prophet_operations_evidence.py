import json
import subprocess
import sys
from pathlib import Path


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
