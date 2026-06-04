# Policy Simulation Evidence Contract v0.1

Status: contract fixture lane

Authority repo: `SocioProphet/prophet-platform`

Upstream measurement authority: `SocioProphet/economic-prophet`

Estate adoption authority: `SocioProphet/sociosphere`

Learning receipt authority: `SocioProphet/systems-learning-loops`

## Purpose

This contract lets Prophet Platform consume a policy-simulation audit artifact as evidence without executing the policy simulation, importing donor runtimes, or treating a simulation score as release authority.

The contract is the platform-facing evidence surface for the AI Economist / Economic Prophet source-intake path. Economic Prophet owns the measurement profile, semantic gates, CLI audit artifact, and triparty quantity calculations. Prophet Platform owns only the product/runtime contract for accepting that artifact into platform evidence consumers.

## Boundary

This is a no-runtime, no-network, no-policy-automation contract lane.

It does not:

- import `SocioProphet/ai-economist`
- execute reinforcement learning or training jobs
- execute live policy changes
- release economic value
- perform external settlement
- mint, redeem, trade, or settle tokens
- claim fairness, legality, production readiness, or policy correctness

## Required evidence

A policy-simulation evidence receipt must carry:

- source repo and source commit for the upstream evidence artifact
- source artifact reference and hash
- Economic Prophet profile ID and run ID
- scenario ID
- advisory-only release authority
- donor runtime dependency flag set to false
- triparty gross/admitted/released/residual quantities
- release and residual ratios
- Sociosphere adoption registry reference
- systems-learning receipt reference
- explicit non-claims

## Semantic gates

The platform must reject evidence if:

1. `runtimeDependency` is not false.
2. `releaseAuthority` is not `advisory_only`.
3. `lambdaAdmit > lambdaEvid`.
4. `lambdaRelease > lambdaAdmit`.
5. `residual != lambdaEvid - lambdaRelease` within tolerance.
6. source, adoption, or learning receipt references are missing.
7. the receipt claims live policy automation, release of value, external settlement, token issuance, or production policy correctness.

## Fixtures

Relevant fixtures:

- `contracts/policy-simulation/evidence-receipt.accepted.example.json`
- `contracts/policy-simulation/evidence-receipt.rejected-runtime-dependency.example.json`

Validate locally:

```bash
python3 tools/validate_policy_simulation_evidence_contract.py
```

## Relationship to platform evidence consumers

This contract is a platform evidence admission surface. It can later feed evidence-receipts, evaluation fabric, professional intelligence workrooms, or governance dashboards, but v0.1 only validates evidence shape and semantic boundary.
