#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts" / "svf"
REQ = BASE / "validate-change-request.example.json"
RES = BASE / "validate-change-response.example.json"
SUM = BASE / "pr-readiness-summary.example.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(name, ok, detail=None):
    return {"check": name, "passed": bool(ok), "detail": detail or []}


def main() -> int:
    req = load(REQ)
    res = load(RES)
    summary = load(SUM)
    out = []

    out.append(check("request-version", req.get("schema_version") == "1.0"))
    out.append(check("request-id", str(req.get("request_id", "")).startswith("svf:validate-change-request:")))
    out.append(check("request-repo", "/" in str(req.get("repo", ""))))
    out.append(check("request-paths", isinstance(req.get("changed_paths"), list) and len(req["changed_paths"]) > 0))
    out.append(check("request-digest", req.get("diff_digest", {}).get("algorithm") in {"sha256", "sha512"}))
    out.append(check("request-actor", bool(req.get("actor", {}).get("actor_id"))))
    out.append(check("request-depth", req.get("validation_depth") in {"advisory", "blocking", "full"}))

    out.append(check("response-version", res.get("schema_version") == "1.0"))
    out.append(check("response-id-match", res.get("request_id") == req.get("request_id")))
    out.append(check("response-repo-match", res.get("repo") == req.get("repo")))
    out.append(check("response-selected", res.get("status") == "selected"))
    plans = res.get("selected_plans", [])
    out.append(check("response-plans", isinstance(plans, list) and len(plans) > 0))
    for i, plan in enumerate(plans):
        out.append(check(f"response-plan-{i}-id", str(plan.get("plan_id", "")).startswith("svf:plan:")))
        out.append(check(f"response-plan-{i}-profile", str(plan.get("profile_id", "")).startswith("svf:profile:")))
        out.append(check(f"response-plan-{i}-mode", plan.get("mode") in {"advisory", "blocking"}))
        out.append(check(f"response-plan-{i}-command", bool(plan.get("validation_command"))))

    warnings = {w.get("code") for w in res.get("warnings", []) if isinstance(w, dict)}
    out.append(check("response-missing-observation-warning", "validation_observation_missing" in warnings))

    out.append(check("summary-version", summary.get("schema_version") == "1.0"))
    out.append(check("summary-repo-match", summary.get("repo") == req.get("repo")))
    out.append(check("summary-not-ready", summary.get("status") == "not_ready"))
    out.append(check("summary-no-receipts", summary.get("receipt_refs") == []))
    out.append(check("summary-no-ready-claims", summary.get("ready_claims") == []))
    findings = {f.get("code") for f in summary.get("advisory_findings", []) if isinstance(f, dict)}
    out.append(check("summary-missing-observation-finding", "validation_observation_missing" in findings))

    response_plan_ids = {p.get("plan_id") for p in plans if isinstance(p, dict)}
    summary_plan_ids = set(summary.get("selected_plans", []))
    out.append(check("summary-plans-match", response_plan_ids == summary_plan_ids, [sorted(response_plan_ids), sorted(summary_plan_ids)]))

    passed = all(item["passed"] for item in out)
    result = {"validator": "svf_agent_contract.v1", "passed": passed, "results": out}
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        print("FAIL: svf agent contract", file=sys.stderr)
        return 1
    print("PASS: svf agent contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
