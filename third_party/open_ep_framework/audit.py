import hashlib
import json
import datetime


def stable_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def write_audit_pack(path: str, run_id: str, scenario: str, framework_version: str, inputs: dict, outputs: dict, overrides=None):
    overrides = overrides or []
    record = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framework_version": framework_version,
        "scenario": scenario,
        "parameter_version": framework_version,
        "input_hash": stable_hash(inputs),
        "output_hash": stable_hash(outputs),
        "inputs": inputs,
        "outputs": outputs,
        "overrides": overrides,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, sort_keys=True)
    return record
