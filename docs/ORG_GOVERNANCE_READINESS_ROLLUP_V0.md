# OrgGov v0 Readiness Rollup

## Purpose

This rollup marks the Organization Governance Control Plane v0 first-pass estate slice as complete and freezes the upstream snapshot used to prepare the next tranche.

The first-pass estate slice proves that the product loop has named contracts, examples, validators, and ownership lanes across the estate:

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

## Upstream review

Before this rollup was created, current `main` heads were checked across the full OrgGov estate because several repos changed after the first tranche. The rollup fixture records those current heads under `upstreamSnapshot.repos`.

The source fixture is:

```text
contracts/orggov/orggov-readiness-rollup.v0.1.example.json
```

Validate it with:

```bash
python3 tools/validate_orggov_readiness_rollup.py
```

## First-pass completion

The v0 first-pass estate slice is complete across eleven repositories:

1. `SocioProphet/prophet-platform`
2. `SocioProphet/ontogenesis`
3. `SocioProphet/prophet-workspace`
4. `SocioProphet/agent-registry`
5. `SocioProphet/policy-fabric`
6. `SocioProphet/agentplane`
7. `SocioProphet/model-governance-ledger`
8. `SocioProphet/delivery-excellence`
9. `SocioProphet/sherlock-search`
10. `SocioProphet/sociosphere`
11. `SourceOS-Linux/sourceos-syncd`

## v0.2 runtime/demo criteria

The next tranche is not another documentation sweep. It should promote the first-pass contracts into a demonstrable runtime path:

- run one end-to-end dogfood workflow from issue to scorecard;
- render the control room from real cross-repo fixtures;
- exercise policy decision states: `allow`, `deny`, `escalate`, `blocked_expected`, `allow_with_constraints`, and `revoke`;
- bind a real or simulated AgentPlane run to work-order evidence;
- emit SourceOS state-integrity binding from a runtime report rather than fixture-only material;
- trace work order → actor → policy → action → evidence → outcome → score through Sherlock.

## Non-goals

- Do not relitigate the first-pass ownership split unless a repo-level contract changes.
- Do not mark v0.2 complete with fixture-only evidence.
- Do not build a generic task manager.
- Do not hide policy, evidence, replay, state integrity, or revocation behind opaque UX.
