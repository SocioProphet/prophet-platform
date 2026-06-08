# DevSecOps Workroom Demo Runbook

Status: operator-facing runbook for the non-production Workroom walkthrough

## Goal

Demonstrate the Prophet Platform DevSecOps Workroom v0.1 as a governed evidence surface, not as a live runtime parity claim.

The audience should leave understanding four things:

1. The Workroom has deterministic report surfaces.
2. The runtime-adjacent bridge connects fixture evidence to reviewable claims.
3. The P2 fixture evidence matrix is complete enough for planning, review, UI surfacing, and CI gating.
4. The system explicitly refuses to certify external/vendor parity or production readiness from fixture evidence.

The demo is a proof-walk, not a fireworks show. Fireworks are how engineering teams accidentally summon procurement demons.

## Demo roles

- Presenter: narrates what the Workroom proves and what it does not prove.
- Operator: runs commands and opens generated/committed artifacts.
- Reviewer: checks claim boundaries and asks whether evidence supports each claim.

One person can play all three roles in a solo walkthrough.

## Demo setup

```bash
cd ~/dev/prophet-platform
git checkout main
git pull --ff-only origin main
git status -sb
```

Expected:

```text
## main...origin/main
```

## 1. Open with the claim boundary

Show:

- `docs/architecture/devsecops-workroom-v0.1-status.md`
- section: `Allowed claims`
- section: `Forbidden claims`
- section: `P2 Runtime Parity Fixture Evidence Matrix`

Narration:

```text
This demo shows a fixture-backed, non-production DevSecOps Workroom evidence spine. It is suitable for planning, review, UI walkthrough, and CI gating. It does not certify live runtime parity, production readiness, or external vendor feature parity.
```

Do not start with the UI. Start with the claim boundary. Otherwise the shiny pixels get elected king.

## 2. Validate the demo-readiness gate

Run:

```bash
python3 tools/validate_devsecops_workroom_demo_readiness.py
```

Expected posture:

- JSON output includes `passed: true`.
- `readiness_state` is `ready_for_nonprod_fixture_review`.
- non-claims are present.

Narration:

```text
The demo-readiness validator checks the existing runtime bridge and status ledger. It does not create a second source of truth; it verifies the bridge, source refs, fixture claim tokens, non-certified boundaries, and P2 matrix documentation.
```

## 3. Validate the runtime parity bridge

Run:

```bash
python3 tools/validate_workroom_runtime_parity_bridge.py
```

Show:

- `artifacts/runtime/workroom-runtime-parity-bridge/fogstack-svf-signadot-readiness.bridge.json`

Narration:

```text
The bridge is the Workroom-facing record that ties persisted runtime-adjacent evidence to allowed and forbidden claims. It records fixture-observed evidence and preserves the boundary against live parity certification.
```

Point to:

- `source_records`
- `observed_evidence`
- `certified_claims`
- `non_certified_claims`
- `non_claims`

## 4. Validate the P2 evidence lanes

Run the fixture evidence validators:

```bash
python3 tools/validate_fogstack_svf_nonprod_sandbox_observation.py
python3 tools/validate_fogstack_svf_baseline_fallback_trace.py
python3 tools/validate_fogstack_svf_network_isolation_observation.py
python3 tools/validate_fogstack_svf_async_topic_isolation_observation.py
python3 tools/validate_fogstack_svf_stateful_resource_isolation_observation.py
python3 tools/validate_fogstack_svf_gitops_reconciliation_observation.py
python3 tools/validate_fogstack_svf_leak_check_observation.py
```

Narration:

```text
These validators prove that the non-production fixture evidence is structurally and semantically present. They do not prove runtime enforcement in a live environment.
```

## 5. Validate the bridge-specific lane checks

Run:

```bash
python3 tools/validate_workroom_runtime_baseline_fallback_bridge.py
python3 tools/validate_workroom_runtime_network_isolation_bridge.py
python3 tools/validate_workroom_runtime_async_topic_isolation_bridge.py
python3 tools/validate_workroom_runtime_stateful_resource_isolation_bridge.py
python3 tools/validate_workroom_runtime_gitops_reconciliation_bridge.py
python3 tools/validate_workroom_runtime_leak_check_bridge.py
```

Narration:

```text
These checks confirm that each evidence lane is linked into the Workroom bridge rather than stranded as isolated JSON confetti.
```

## 6. Build and inspect the deterministic report surface

Run:

```bash
python3 tools/smoke_build_devsecops_workroom_report.py
```

Show the canonical report artifacts referenced by the smoke builder.

Narration:

```text
The report surface gives a stable review artifact. It is designed for repeatability and drift detection, not theatrical dashboard vapor.
```

## 7. Show the UI/API path, if running locally

If the local gateway/web stack is available, show the fixture-mode endpoints and UI card that expose the Workroom report and runtime parity bridge.

Primary surfaces:

- `GET /v1/workroom/report`
- `GET /v1/workroom/report.md`
- `GET /v1/workroom/runtime-parity-bridge`
- Workroom web card rendering for runtime parity bridge

Narration:

```text
The UI is a projection of evidence. It is not the evidence itself. The evidence remains the committed artifacts and validators.
```

## 8. Close with the decision state

Close on the P2 matrix and bridge decision state.

Approved close:

```text
The Workroom is demo-ready for non-production fixture review. It has a complete fixture-backed runtime-parity evidence spine for planning, review, UI surfacing, and CI gating. The next tranche is live/runtime evidence, which remains outside the current claim boundary.
```

Forbidden close:

```text
We have full live runtime parity.
We are production-ready.
We have certified external vendor parity.
The platform can remediate production automatically.
```

## One-command minimum proof path

For a short proof run:

```bash
python3 tools/validate_devsecops_workroom_demo_readiness.py && \
python3 tools/validate_workroom_runtime_parity_bridge.py && \
python3 tools/smoke_build_devsecops_workroom_report.py
```

## Full local proof path

For a complete local proof run:

```bash
python3 tools/validate_devsecops_workroom_demo_readiness.py && \
python3 tools/validate_workroom_runtime_parity_bridge.py && \
python3 tools/validate_workroom_runtime_parity_ui_component.py && \
python3 tools/validate_fogstack_svf_nonprod_sandbox_observation.py && \
python3 tools/validate_fogstack_svf_baseline_fallback_trace.py && \
python3 tools/validate_fogstack_svf_network_isolation_observation.py && \
python3 tools/validate_fogstack_svf_async_topic_isolation_observation.py && \
python3 tools/validate_fogstack_svf_stateful_resource_isolation_observation.py && \
python3 tools/validate_fogstack_svf_gitops_reconciliation_observation.py && \
python3 tools/validate_fogstack_svf_leak_check_observation.py && \
python3 tools/validate_workroom_runtime_baseline_fallback_bridge.py && \
python3 tools/validate_workroom_runtime_network_isolation_bridge.py && \
python3 tools/validate_workroom_runtime_async_topic_isolation_bridge.py && \
python3 tools/validate_workroom_runtime_stateful_resource_isolation_bridge.py && \
python3 tools/validate_workroom_runtime_gitops_reconciliation_bridge.py && \
python3 tools/validate_workroom_runtime_leak_check_bridge.py && \
python3 tools/smoke_build_devsecops_workroom_report.py
```

## Demo evidence checklist

Before presenting, confirm:

- status ledger exists and includes the P2 matrix;
- runtime parity bridge exists;
- demo-readiness validator passes;
- runtime bridge validator passes;
- report smoke passes;
- UI/API surfaces are presented only as projections of committed evidence;
- forbidden claims are stated explicitly.

## Non-claims

This runbook does not execute external infrastructure.

This runbook does not inspect production systems.

This runbook does not certify production readiness.

This runbook does not certify external vendor feature parity.

This runbook does not authorize remediation.
