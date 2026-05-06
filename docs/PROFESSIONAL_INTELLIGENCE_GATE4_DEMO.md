# Professional Intelligence Gate 4 Demo

## Purpose

This runbook defines the first local verification path for the Professional Intelligence OS Gate 4 demo.

Gate 4 is the first integrated demo lane. It verifies that the platform can trace the demo sequence across the merged Professional Intelligence artifacts:

1. playbook;
2. context query;
3. policy and obligation checks;
4. route decision;
5. runtime controls;
6. Agentplane run reference;
7. workroom reference;
8. evidence references;
9. adoption event reference.

The runner is intentionally record-only. It does not call external services or live providers. It verifies the orchestration contract and emits local reports for DelEx acceptance.

## Inputs

Default orchestration fixture:

```text
contracts/orchestration/pi-gate4-demo.v0.1.example.json
```

Default verification report:

```text
build/professional-intelligence/gate4-demo-verification.json
```

Default dashboard control-state export:

```text
build/professional-intelligence/dashboard-control-state.json
```

Default Agentplane smoke summary:

```text
build/professional-intelligence/agentplane-smoke-summary.json
```

## Command

```bash
python3 tools/run_professional_intelligence_gate4_demo.py
python3 tools/export_professional_intelligence_dashboard_state.py
python3 tools/summarize_professional_intelligence_agentplane_smoke.py
```

To make Agentplane smoke artifacts mandatory, use:

```bash
python3 tools/summarize_professional_intelligence_agentplane_smoke.py --required
```

## Validation bundle

Run platform Professional Intelligence validation first:

```bash
python3 tools/validate_professional_intelligence.py
```

Then run the Gate 4 verifier, dashboard export, and Agentplane smoke summary:

```bash
python3 tools/run_professional_intelligence_gate4_demo.py
python3 tools/export_professional_intelligence_dashboard_state.py
python3 tools/summarize_professional_intelligence_agentplane_smoke.py
```

For full repository validation:

```bash
python3 tools/validate_repo.py
```

## Acceptance criteria

The verification report must show:

- `passed: true`;
- non-empty workroom reference;
- non-empty playbook reference;
- non-empty context query reference;
- non-empty context pack references;
- non-empty search packet references;
- non-empty policy decision references;
- non-empty obligation references;
- non-empty route decision references;
- non-empty runtime control references;
- non-empty agent authority references;
- non-empty Agentplane run references;
- non-empty ledger references;
- non-empty evidence references;
- non-empty adoption event references;
- all required Gate 4 steps present;
- every step requires evidence;
- every step has input and output references.

The dashboard control-state export must show:

- `kind: ProfessionalIntelligenceDashboardControlState`;
- `verificationPassed: true`;
- non-empty metric list;
- non-empty gate list;
- non-empty `nextMoves` list;
- source report and orchestration references.

The Agentplane smoke summary must exist. It may be non-blocking when artifacts are not present locally. Use `--required` when validating a workspace that has already run the Agentplane host smoke.

## Expected report kinds

```json
{
  "kind": "ProfessionalIntelligenceGate4DemoVerification",
  "passed": true
}
```

```json
{
  "kind": "ProfessionalIntelligenceDashboardControlState",
  "verificationPassed": true
}
```

```json
{
  "kind": "ProfessionalIntelligenceAgentplaneSmokeSummary"
}
```

## Current completion impact

This runner, exporter, and Agentplane smoke summarizer move the Professional Intelligence OS from a validated orchestration object to a locally verifiable demo record plus dashboard and optional Agentplane artifact summaries.

Expected completion movement once merged:

- Overall alignment: 74% -> 77%.
- Runtime implementation: 52% -> 58%.
- Demo readiness: 80% -> 83%.
- Cybernetic controls: 58% -> 62%.

## Non-goals

- This runner does not execute live model calls.
- This runner does not call external SaaS or hosted providers.
- This runner does not mutate workrooms.
- This runner does not replace Agentplane runtime execution.
- This runner does not replace DelEx demo acceptance; it emits reports DelEx can evaluate.
