#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

TOOL_VERSION = "0.1"


def load_doc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if yaml is None:
        raise SystemExit("ERR: PyYAML is required to verify YAML Fog Stack bundles")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected mapping at top level: {path}")
    return data


def get_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def array_dict_field_values(bundle: dict[str, Any], path: str, field: str) -> list[Any]:
    arr = get_path(bundle, path) or []
    if not isinstance(arr, list):
        return []
    out: list[Any] = []
    for item in arr:
        if isinstance(item, dict) and field in item:
            out.append(item[field])
    return out


def eval_when(bundle: dict[str, Any], when: dict[str, Any] | None) -> bool:
    if not when:
        return True
    actual = get_path(bundle, when["path"])
    if "equals" in when:
        return actual == when["equals"]
    if "in" in when:
        return actual in when["in"]
    return bool(actual)


def rule_check(bundle: dict[str, Any], rule: dict[str, Any]) -> tuple[str, str]:
    check = rule["check"]
    op = check["op"]

    if op == "path_true":
        val = get_path(bundle, check["path"])
        return ("pass", "ok") if val is True else ("fail", f"expected {check['path']} == true, got {val!r}")

    if op == "path_equals":
        val = get_path(bundle, check["path"])
        return ("pass", "ok") if val == check["value"] else ("fail", f"expected {check['path']} == {check['value']!r}, got {val!r}")

    if op == "path_not_in":
        val = get_path(bundle, check["path"])
        return ("pass", "ok") if val not in check["values"] else ("fail", f"value {val!r} is forbidden for {check['path']}")

    if op == "path_contains_all":
        arr = get_path(bundle, check["path"]) or []
        if not isinstance(arr, list):
            return ("fail", f"{check['path']} is not a list")
        missing = [x for x in check["values"] if x not in arr]
        return ("pass", "ok") if not missing else ("fail", "missing values: " + ", ".join(missing))

    if op == "array_objects_field_contains_all":
        vals = array_dict_field_values(bundle, check["path"], check["field"])
        missing = [x for x in check["values"] if x not in vals]
        return ("pass", "ok") if not missing else ("fail", "missing values: " + ", ".join(missing))

    if op == "supported_profiles_all_false":
        arr = get_path(bundle, check["path"]) or []
        if not isinstance(arr, list):
            return ("fail", f"{check['path']} is not a list")
        offenders = []
        for item in arr:
            if isinstance(item, dict) and item.get("status") == "supported" and item.get(check["field"]) is not False:
                offenders.append(item.get("id", "<unknown>"))
        return ("pass", "ok") if not offenders else ("fail", f"supported profiles violate {check['field']}=false: {', '.join(offenders)}")

    if op == "supported_profiles_any_match":
        arr = get_path(bundle, check["path"]) or []
        if not isinstance(arr, list):
            return ("fail", f"{check['path']} is not a list")
        criteria = check["criteria"]
        for item in arr:
            if isinstance(item, dict) and item.get("status") == "supported" and all(item.get(k) == v for k, v in criteria.items()):
                return ("pass", "ok")
        return ("fail", f"no supported profile matched {criteria!r}")

    if op == "path_lte":
        val = get_path(bundle, check["path"])
        try:
            ok = val <= check["value"]
        except Exception:
            ok = False
        return ("pass", "ok") if ok else ("fail", f"expected {check['path']} <= {check['value']!r}, got {val!r}")

    return ("fail", f"unknown op: {op}")


def summarize(checks: list[dict[str, Any]]) -> tuple[str, int, dict[str, int]]:
    counts = {"warning": 0, "error": 0, "critical": 0}
    status = "pass"
    for item in checks:
        if item["status"] != "fail":
            continue
        sev = item["severity"]
        if sev in ("warning", "warn"):
            counts["warning"] += 1
            if status == "pass":
                status = "warn"
        elif sev == "error":
            counts["error"] += 1
            status = "fail"
        elif sev == "critical":
            counts["critical"] += 1
            status = "fail"
        else:
            counts["error"] += 1
            status = "fail"
    exit_code = 0 if counts["critical"] == 0 and counts["error"] == 0 else 2
    return status, exit_code, counts


def verify(bundle_path: Path, rulepack_path: Path) -> dict[str, Any]:
    bundle = load_doc(bundle_path)
    rulepack = load_doc(rulepack_path)
    checks: list[dict[str, Any]] = []
    for rule in rulepack.get("rules", []):
        if not eval_when(bundle, rule.get("when")):
            checks.append({"id": rule["id"], "severity": rule["severity"], "status": "skip", "message": "condition not met"})
            continue
        state, msg = rule_check(bundle, rule)
        checks.append({"id": rule["id"], "severity": rule["severity"], "status": state, "message": msg})
    status, exit_code, counts = summarize(checks)
    return {
        "tool": "fogstack verify",
        "version": TOOL_VERSION,
        "subject": {
            "kind": bundle.get("kind", "FogStackBundle"),
            "bundle_id": get_path(bundle, "metadata.bundle_id"),
            "bundle_version": get_path(bundle, "metadata.version"),
            "path": str(bundle_path),
        },
        "summary": {
            "status": status,
            "exit_code": exit_code,
            "checks_run": len(checks),
            "warnings": counts["warning"],
            "errors": counts["error"],
            "critical": counts["critical"],
        },
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype Fog Stack bundle verifier")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--rulepack", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bundle = load_doc(args.bundle)
    bundle_id = get_path(bundle, "metadata.bundle_id")
    default_rulepack = Path(__file__).resolve().parents[1] / "conformance" / "rulepacks" / f"{bundle_id}-v0.1.yaml"
    result = verify(args.bundle, args.rulepack or default_rulepack)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"{result['subject']['bundle_id']} status={s['status']} checks={s['checks_run']} warnings={s['warnings']} errors={s['errors']} critical={s['critical']}")
        for item in result["checks"]:
            print(f"- {item['status'].upper():5s} {item['id']} [{item['severity']}] {item['message']}")
    return result["summary"]["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
