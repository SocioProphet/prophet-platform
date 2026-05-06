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

The runner is intentionally record-only. It does not call external services or live providers. It verifies the orchestration contract and emits a local report for DelEx acceptance.

## Inputs

Default orchestration fixture:

```text
contracts/orchestration/pi-gate4-demo.v0.1.example.json
```

Default output report:

```text
build/professional-intelligence/gate4-demo-verification.json
```

## Command

```bash
python3 tools/run_professional_intelligence_gate4_demo.py
```

To provide explicit paths:

```bash
python3 tools/run_professional_intelligence_gate4_demo.py \
  --orchestration contracts/orchestration/pi-gate4-demo.v0.1.example.json \
  --output build/professional-intelligence/gate4-demo-verification.json
```

## Validation bundle

Run platform Professional Intelligence validation first:

```bash
python3 tools/validate_professional_intelligence.py
```

Then run the Gate 4 verifier:

```bash
python3 tools/run_professional_intelligence_gate4_demo.py
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

## Expected report kind

```json
{
  "kind": "ProfessionalIntelligenceGate4DemoVerification",
  "passed": true
}
```

## Current completion impact

This runner moves the Professional Intelligence OS from a validated orchestration object to a locally verifiable demo record.

Expected completion movement once merged:

- Overall alignment: 68% -> 72%.
- Runtime implementation: 42% -> 48%.
- Demo readiness: 70% -> 76%.
- Cybernetic controls: 50% -> 54%.

## Non-goals

- This runner does not execute live model calls.
- This runner does not call external SaaS or hosted providers.
- This runner does not mutate workrooms.
- This runner does not replace Agentplane runtime execution.
- This runner does not replace DelEx demo acceptance; it emits the report DelEx can evaluate.
