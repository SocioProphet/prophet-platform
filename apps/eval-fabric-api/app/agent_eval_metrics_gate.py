"""Fail-closed gate for the agent eval metrics.

Reads an :class:`~app.agent_eval_metrics.EvalBatch` payload (a JSON file),
computes the metric contract, and exits NON-ZERO when a safety-relevant metric
breaches — ``refusalScore`` below its floor OR ``anomalyStatus == anomalous``.
A breach therefore fails the build.

Usage::

    python3 -m app.agent_eval_metrics_gate <payload.json>

Exit codes:
    0  healthy — no breach
    2  breach — refusalScore below floor and/or anomalyStatus anomalous
    3  usage / input error (fails closed: unreadable input is not "healthy")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .agent_eval_metrics import compute_all_from_payload, gate_breaches


def run_gate(payload: dict) -> int:
    result = compute_all_from_payload(payload)
    metrics = result["metrics"]
    print("agent-eval-metrics gate")
    print(f"  agent_id           : {result.get('agent_id')}")
    print(f"  eigenStability     : {metrics['eigenStability']:.4f}  (LOW = stable)")
    print(f"  typologyScore      : {metrics['typologyScore']:.2f}  (0..100)")
    print(f"  interactionQuality : {metrics['interactionQuality']:.4f}  (0..1)")
    print(f"  refusalScore       : {metrics['refusalScore']:.4f}  (0..1)")
    print(f"  anomalyStatus      : {metrics['anomalyStatus']}")

    breaches = gate_breaches(result)
    if breaches:
        print("GATE: FAIL (fail-closed) — breaches:")
        for b in breaches:
            print(f"  - {b}")
        return 2
    print("GATE: PASS — no refusal/anomaly breach")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 -m app.agent_eval_metrics_gate <payload.json>", file=sys.stderr)
        return 3
    path = Path(argv[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # fail closed on bad input
        print(f"cannot read/parse payload {path}: {exc}", file=sys.stderr)
        return 3
    return run_gate(payload)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
