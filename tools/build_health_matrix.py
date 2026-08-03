#!/usr/bin/env python3
"""build_health_matrix — the agentic shell's center-canvas health matrix.

Aggregates per-repo operational signals into a RepoHealthMatrix (Workflow A:
group health audit): CI health, security posture, docs freshness, last activity,
plus a derived agent finding, proposed action, and risk tier. Signal collection
(gh I/O) is separated from classification (pure, tested), and the matrix can be
materialized into an AgenticTask (matrix -> task) so the shell's center canvas
and object model compose.

  build_health_matrix.py --from signals.json          # from a signals fixture
  build_health_matrix.py --org SocioProphet           # collect via gh
  build_health_matrix.py --from signals.json --to-task # emit an AgenticTask too

Conforms to contracts/RepoHealthMatrix.v0.1.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

DIMENSIONS = ["ci_health", "security_posture", "docs_freshness", "last_activity"]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---- classification (pure) --------------------------------------------------
def _ci(conclusion: str | None) -> str:
    return {"success": "ok", "failure": "fail", "cancelled": "warn", "timed_out": "fail"}.get(
        (conclusion or "").lower(), "unknown")


def _security(open_alerts: int | None) -> str:
    if open_alerts is None:
        return "unknown"
    return "ok" if open_alerts == 0 else "warn" if open_alerts < 5 else "fail"


def _age(days: int | None, ok_lt: int, warn_lt: int) -> str:
    if days is None:
        return "unknown"
    return "ok" if days < ok_lt else "warn" if days < warn_lt else "fail"


def classify_row(sig: dict[str, Any]) -> dict[str, Any]:
    """Turn one repo's raw signals into a scored matrix row + a proposed action.
    A row proposes only *draft* (reversible) actions; the risk_tier reflects the
    severity of what the operator would then approve."""
    ci = _ci(sig.get("latest_ci_conclusion"))
    sec = _security(sig.get("open_security_alerts"))
    docs = "fail" if not sig.get("has_readme", True) else _age(sig.get("readme_age_days"), 180, 365)
    act = _age(sig.get("pushed_age_days"), 30, 90)
    owner = sig.get("owner")
    has_owner = bool(owner) or bool(sig.get("has_codeowners"))

    findings: list[str] = []
    if ci == "fail":
        findings.append("CI failing")
    if sec == "fail":
        findings.append("critical security alerts")
    elif sec == "warn":
        findings.append("open security alerts")
    if docs == "fail":
        findings.append("stale/missing docs")
    if act == "fail":
        findings.append("no recent activity")
    if not has_owner:
        findings.append("no maintainer/CODEOWNERS")

    # risk tier of the remediation the operator would approve (deny wins upward)
    if sec == "fail":
        tier, action = "high", "stage security remediation (needs explicit approval + evidence)"
    elif ci == "fail" or not has_owner:
        tier, action = "medium", "draft issue + propose owner (contextual review)"
    elif findings:
        tier, action = "low", "draft issue (auto-stage, batch-approve)"
    else:
        tier, action = "low", "no action — healthy"

    return {
        "resource": sig["resource"],
        "owner": owner,
        "ci_health": ci,
        "security_posture": sec,
        "docs_freshness": docs,
        "last_activity": act,
        "agent_finding": "; ".join(findings) if findings else "healthy",
        "proposed_action": action,
        "risk_tier": tier,
        "evidence_refs": sig.get("evidence_refs", []),
    }


def build_matrix(signals: list[dict[str, Any]], scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "version": "0.1",
        "generated_at": _utc(),
        "scope": scope or {},
        "dimensions": DIMENSIONS,
        "rows": sorted((classify_row(s) for s in signals), key=lambda r: r["resource"]),
    }


# ---- signal collection (gh I/O) ---------------------------------------------
def collect_signals_gh(org: str, limit: int = 100) -> list[dict[str, Any]]:
    """Best-effort collection via the gh CLI. Network I/O — not exercised in the
    hermetic tests (those use a signals fixture)."""
    def gh(args: list[str]) -> Any:
        r = subprocess.run(["gh", *args], text=True, capture_output=True, timeout=30)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None

    repos = gh(["repo", "list", org, "--limit", str(limit), "--json",
                "name,pushedAt,defaultBranchRef"]) or []
    now = datetime.now(timezone.utc)
    signals = []
    for repo in repos:
        full = f"{org}/{repo['name']}"
        pushed = repo.get("pushedAt")
        pushed_age = None
        if pushed:
            pushed_age = (now - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days
        runs = gh(["run", "list", "-R", full, "-L", "1", "--json", "conclusion"]) or []
        signals.append({
            "resource": full,
            "pushed_age_days": pushed_age,
            "latest_ci_conclusion": (runs[0].get("conclusion") if runs else None),
            # security/docs/owner signals require extra calls; left None (=> unknown) here
        })
    return signals


# ---- matrix -> AgenticTask (composition) ------------------------------------
def matrix_to_task(matrix: dict[str, Any], owner: str = "human:local-user") -> dict[str, Any]:
    """Materialize Workflow A as an AgenticTask: one staged/proposed action per
    non-healthy row. Requires the AgenticTask engine (prophet-platform#1245)."""
    import agentic_task as at  # lazy — depends on the AgenticTask contract PR
    scope = matrix.get("scope", {})
    t = at.new_task(f"Group health audit ({scope.get('selector') or scope})", owner=owner,
                    autonomy_level="L2", scope=scope)
    for row in matrix["rows"]:
        if row["risk_tier"] == "low" and row["agent_finding"] == "healthy":
            continue
        at.add_action(t, capability=f"health.{row['risk_tier']}", risk_tier=row["risk_tier"],
                      why=f"{row['resource']}: {row['agent_finding']} -> {row['proposed_action']}",
                      args={"resource": row["resource"], "action": row["proposed_action"]},
                      evidence_refs=row.get("evidence_refs", []))
    at.transition(t, "ready", actor=owner)
    at.transition(t, "running")
    if t["approval_requirements"]["requires_human"]:
        at.transition(t, "waiting_for_approval", reason=t["approval_requirements"]["reason"])
    return t


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a RepoHealthMatrix (shell center canvas).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from", dest="from_file", help="a signals JSON fixture")
    src.add_argument("--org", help="collect signals from a GitHub org via gh")
    ap.add_argument("--to-task", action="store_true", help="also emit an AgenticTask")
    args = ap.parse_args(argv)

    if args.from_file:
        payload = json.loads(open(args.from_file).read())
        signals, scope = payload["signals"], payload.get("scope", {})
    else:
        signals, scope = collect_signals_gh(args.org), {"orgs": [args.org]}

    matrix = build_matrix(signals, scope)
    out: dict[str, Any] = {"matrix": matrix}
    if args.to_task:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
        out["task"] = matrix_to_task(matrix)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
