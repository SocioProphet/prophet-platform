# Prophet Platform Demo Package Index

Status: navigation index for current non-production demo surfaces

## Purpose

This directory collects the operator-facing demo materials for Prophet Platform. The current primary demo is the DevSecOps Workroom v0.1 non-production evidence walkthrough.

The demo package is intentionally evidence-first. It shows committed artifacts, validators, report surfaces, and claim boundaries before showing any UI projection. Shiny dashboards are nice; ungrounded dashboards are raccoons in tuxedos.

## Current primary demo

### DevSecOps Workroom non-production demo

Use this demo to show that Prophet Platform has a fixture-backed DevSecOps Workroom evidence spine suitable for planning, review, UI surfacing, and CI gating.

Primary materials:

| Material | Path | Use |
| --- | --- | --- |
| Status ledger | `docs/architecture/devsecops-workroom-v0.1-status.md` | Authoritative state, allowed claims, forbidden claims, P2 matrix |
| Local walkthrough | `docs/demo/devsecops-workroom-nonprod-demo-walkthrough.md` | Local operator validation sequence |
| Presentation runbook | `docs/demo/devsecops-workroom-demo-runbook.md` | Presenter-facing demo order and narration |
| Runtime bridge | `artifacts/runtime/workroom-runtime-parity-bridge/fogstack-svf-signadot-readiness.bridge.json` | Evidence-to-claim bridge |
| Demo-readiness validator | `tools/validate_devsecops_workroom_demo_readiness.py` | Readiness gate over existing bridge and ledger |
| Focused workflow | `.github/workflows/devsecops-workroom-demo-readiness.yml` | CI validation surface for demo-readiness gate |

## Minimum local proof path

From repo root:

```bash
python3 tools/validate_devsecops_workroom_demo_readiness.py && \
python3 tools/validate_workroom_runtime_parity_bridge.py && \
python3 tools/smoke_build_devsecops_workroom_report.py
```

This proves the demo-readiness gate, runtime parity bridge, and deterministic Workroom report surface.

## Full local proof path

For a fuller proof run, use the command sequence in:

```text
docs/demo/devsecops-workroom-demo-runbook.md
```

That sequence validates the P2 evidence lanes, bridge-specific lane checks, UI wiring, and report surface.

## Allowed top-level demo claim

```text
Prophet Platform has a v0.1 fixture-backed DevSecOps Workroom evidence spine suitable for non-production planning, review, UI walkthrough, and CI gating.
```

## Forbidden top-level demo claims

Do not claim:

```text
Full external runtime parity.
Production readiness.
Certified live runtime parity.
Autonomous production remediation.
Confirmed incident causality from fixture evidence alone.
```

## Demo order

Recommended order:

1. Open the status ledger and claim boundaries.
2. Run the demo-readiness validator.
3. Run the runtime bridge validator.
4. Run the deterministic Workroom report smoke.
5. Show the bridge artifact and P2 matrix.
6. Show UI/API projections only after the evidence has been established.
7. Close by restating non-production scope and next live/runtime evidence tranche.

## Non-claims

This index does not execute infrastructure.

This index does not certify production readiness.

This index does not certify external vendor parity.

This index does not authorize remediation.
