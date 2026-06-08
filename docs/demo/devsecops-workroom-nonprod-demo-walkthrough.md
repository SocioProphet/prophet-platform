# DevSecOps Workroom Non-Production Demo Walkthrough

Status: executable demo script for fixture-backed review

## Purpose

This walkthrough gives an operator a clean local path for demonstrating the DevSecOps Workroom v0.1 evidence spine without overstating the runtime claim.

The demo shows:

- deterministic Workroom report generation;
- runtime parity bridge validation;
- P2 fixture evidence matrix presence;
- demo-readiness validation;
- explicit claim boundaries.

It does not demonstrate production runtime parity or external vendor feature parity. This is fixture-backed review, not a magic wand. The wand is still plastic.

## Preconditions

Run from a clean checkout of `SocioProphet/prophet-platform` on `main`.

```bash
cd ~/dev/prophet-platform
git checkout main
git pull --ff-only origin main
git status -sb
```

Expected clean state:

```text
## main...origin/main
```

## Core validation sequence

Run the focused Workroom validations first:

```bash
python3 tools/validate_workroom_runtime_parity_bridge.py
python3 tools/validate_workroom_runtime_parity_ui_component.py
python3 tools/validate_devsecops_workroom_demo_readiness.py
python3 tools/smoke_build_devsecops_workroom_report.py
```

Expected posture:

- runtime parity bridge validator passes;
- UI wiring validator passes;
- demo-readiness validator reports `ready_for_nonprod_fixture_review`;
- Workroom report smoke passes.

## Runtime-adjacent evidence sequence

To show the P2 fixture-backed evidence spine, run:

```bash
python3 tools/validate_fogstack_svf_nonprod_sandbox_observation.py
python3 tools/validate_fogstack_svf_baseline_fallback_trace.py
python3 tools/validate_fogstack_svf_network_isolation_observation.py
python3 tools/validate_fogstack_svf_async_topic_isolation_observation.py
python3 tools/validate_fogstack_svf_stateful_resource_isolation_observation.py
python3 tools/validate_fogstack_svf_gitops_reconciliation_observation.py
python3 tools/validate_fogstack_svf_leak_check_observation.py
```

Optional bridge-specific checks:

```bash
python3 tools/validate_workroom_runtime_baseline_fallback_bridge.py
python3 tools/validate_workroom_runtime_network_isolation_bridge.py
python3 tools/validate_workroom_runtime_async_topic_isolation_bridge.py
python3 tools/validate_workroom_runtime_stateful_resource_isolation_bridge.py
python3 tools/validate_workroom_runtime_gitops_reconciliation_bridge.py
python3 tools/validate_workroom_runtime_leak_check_bridge.py
```

## Report surface

Build the deterministic Workroom report surface:

```bash
python3 tools/smoke_build_devsecops_workroom_report.py
```

Then inspect the canonical report artifacts referenced by the smoke test. The exact output path is intentionally owned by the report builder so drift detection remains centralized.

## Demo narrative

Use this language:

```text
The DevSecOps Workroom v0.1 has a fixture-backed, non-production evidence spine for review. It exposes deterministic Workroom reports, a runtime-adjacent parity bridge, a P2 fixture evidence matrix, and a demo-readiness validator. The system is suitable for planning, review, UI walkthrough, and CI gating of the fixture contract.
```

Do not use this language:

```text
The platform has full external runtime parity.
The platform is production ready.
The platform has certified live parity.
The platform can autonomously remediate production systems.
The platform proves real incident causality from fixture evidence alone.
```

## Current validation anchors

The current demo-readiness spine is anchored by:

- `tools/validate_devsecops_workroom_demo_readiness.py`;
- `.github/workflows/devsecops-workroom-demo-readiness.yml`;
- `docs/architecture/devsecops-workroom-v0.1-status.md`;
- `artifacts/runtime/workroom-runtime-parity-bridge/fogstack-svf-signadot-readiness.bridge.json`.

## Completion test

A local operator can consider the non-production demo walkthrough ready when the following pass:

```bash
python3 tools/validate_devsecops_workroom_demo_readiness.py && \
python3 tools/validate_workroom_runtime_parity_bridge.py && \
python3 tools/smoke_build_devsecops_workroom_report.py
```

## Non-claims

This walkthrough does not execute external infrastructure.

This walkthrough does not inspect production systems.

This walkthrough does not certify production readiness.

This walkthrough does not certify external vendor feature parity.

This walkthrough does not authorize remediation.
