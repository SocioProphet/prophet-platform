#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "repo-governance-mvp"
FINDINGS = BUILD / "repo-governance-findings.json"
REQUESTS = BUILD / "repo-governance-policy-requests.json"
OUTPUT = BUILD / "repo-governance-readout.md"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def render() -> str:
    findings = load_json(FINDINGS)
    requests = load_json(REQUESTS)

    lines: list[str] = []
    lines.append("# Repo Governance MVP Readout")
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    for finding in findings:
        lines.append(f"### {finding['finding_id']}")
        lines.append(f"- Repository: `{finding['subject_repository']}`")
        lines.append(f"- Kind: `{finding['kind']}`")
        lines.append(f"- Severity: `{finding['severity']}`")
        lines.append(f"- Rule: `{finding['rule_id']}`")
        lines.append(f"- Action status: `{finding['action_status']}`")
        lines.append(f"- Policy required: `{finding['policy_decision_required']}`")
        lines.append(f"- Reason: {finding['reason']}")
        lines.append("")

    lines.append("## Policy Requests")
    lines.append("")

    for request in requests:
        lines.append(f"### {request['request_id']}")
        lines.append(f"- Repository: `{request['subject_repository']}`")
        lines.append(f"- Requested decision: `{request['requested_decision']}`")
        lines.append(f"- Action status: `{request['action_status']}`")
        lines.append(f"- Reason: {request['reason']}")
        lines.append("")

    lines.append("## Safety Boundary")
    lines.append("")
    lines.append("All findings are advisory only. No repository mutation or runtime action is authorized by this MVP.")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"OK: wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
