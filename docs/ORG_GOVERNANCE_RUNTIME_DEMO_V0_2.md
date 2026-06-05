# OrgGov v0.2 Runtime Demo

## Purpose

OrgGov v0.2 promotes the v0 first-pass estate slice from static contract capture into a demonstrable runtime path.

The v0.1 readiness rollup proved that the estate has an aligned contract spine across eleven repos. The v0.2 runtime-demo spine defines what must execute before we can call OrgGov buyer-visible rather than fixture-backed.

## Product loop

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

## Demo status

The current v0.2 spine is `fixture_backed`.

That means the estate has enough contract material to render the path, but not yet enough runtime evidence to claim a live demo. The fixture explicitly separates `fixtureEvidenceRefs` from `runtimeEvidenceRefs` so we do not accidentally promote static records into runtime proof.

## Contract files

- `contracts/orggov/orggov-runtime-demo.v0.2.schema.json`
- `contracts/orggov/orggov-runtime-demo.v0.2.example.json`
- `tools/validate_orggov_runtime_demo.py`

## Required runtime stages

The v0.2 demo path must cover:

1. GitHub issue/work order binding.
2. Professional Workroom control-room render.
3. Actor, role, authority, grant, and revocation posture.
4. Policy state coverage for `allow`, `allow_with_constraints`, `deny`, `escalate`, `blocked_expected`, and `revoke`.
5. AgentPlane validation, placement, run, replay, and session evidence.
6. Model/tool/context/eval receipt linkage.
7. SourceOS state-integrity binding emitted from runtime report posture.
8. Sherlock trace across work order, actor, policy, action, evidence, outcome, score, and learning.
9. Delivery Excellence scorecard update.
10. Sociosphere topology and propagation check.

## Runtime promotion criteria

The demo can promote beyond `fixture_backed` only when:

- at least one work order is generated or bound by a live workflow step;
- all six policy states are exercised with replayable evidence;
- AgentPlane produces concrete validation, placement, run, replay, and session artifacts;
- SourceOS emits a state-integrity binding from report posture;
- Sherlock traces work order to evidence, outcome, score, and learning event;
- Delivery Excellence scorecard is computed from demo evidence rather than hand-entered values;
- the demo remains non-secret and does not expose credentials or private local state.

## Non-goals

- Do not call fixture-only evidence runtime proof.
- Do not bypass policy gates for demo speed.
- Do not hide replay, state-integrity, revocation, or search gaps.
- Do not turn the control plane into a generic task board.
