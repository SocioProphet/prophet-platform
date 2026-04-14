# NG TOM Benefits Instrumentation v1

## Purpose

The 10/20/60 figures from the slide set are benchmark caps tied to automation class, not bottom-up savings forecasts. This document defines the minimum instrumentation required to turn them into a defensible business case.

## Benefit formula

For capability `c` in period `t`:

`GrossProductivityBenefit(c,t) = BaselineSpend(c,t) × BenchmarkCap(c) × ScopeFactor(c,t) × Adoption(c,t) × AutomationMaturity(c,t) × Confidence(c,t)`

Then split into:
- `HardSavings = GrossProductivityBenefit × RealizationRate`
- `CapacityReleased = GrossProductivityBenefit × (1 - RealizationRate)`

Then add:
- non-labor benefit
- risk avoidance
- top-side benefit

Then subtract:
- transition cost
- dual-run cost
- stranded cost

## Required instrumentation

| Dimension | Minimum evidence |
|---|---|
| Baseline spend | Capability-level cost baseline, including labor and non-labor |
| Scope factor | Explicit scope statement and excluded sub-activities |
| Adoption | Share of demand routed through the governed platform path |
| Automation maturity | Automated steps, manual fallbacks, and exception rates |
| Confidence | Credibility haircut tied to local conditions and control gaps |
| Realization rate | Portion booked as hard savings versus redeployed capacity |
| Top-side value | Journey-facing operational or commercial lift |
| Risk avoidance | Incident, outage, audit, or compliance cost reduction |

## Benefit-credit gates

Benefits should only be booked when all applicable gates are true:
1. Standard blueprint exists
2. Request volume is flowing through catalog/API
3. Manual approvals are removed or materially reduced
4. Instances auto-register into service/asset inventory
5. Run-state hooks are automatic
6. Evidence collection is automatic
7. The old path is retired or usage-capped

## Scenario structure

Use prudent, base, and stretch scenarios. Vary adoption, maturity, realization rate, and confidence independently.
