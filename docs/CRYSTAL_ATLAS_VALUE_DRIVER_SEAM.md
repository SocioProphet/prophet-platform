# Crystal Atlas → value-driver seam

Wires the **value-driver mechanism into the competitive-intelligence lane**. Prior
to this, Crystal Atlas findings and the value-driver/valuation tooling were
disconnected (no cross-reference in either direction). This seam closes that gap.

## What it does

`intel.value_driver.scored.v0` (in `contracts/crystal-atlas/events`) takes a
Crystal Atlas **downstream finding** and attaches an equity-weighted value-driver
breakdown plus an overall value score, so a finding arrives **quantified** rather
than raw:

| Source finding | Value drivers |
|---|---|
| `procurement.substitution.recommended.v0` | Cost Efficiency, Switching Risk, Continuity |
| `diligence.risk.pack.generated.v0` | Risk Exposure (inverted), Coverage Completeness |
| `entitlement.adjacency.inferred.v0` | Expansion Potential |
| `contract.clauses.compared.v0` | Change Materiality |
| (unknown) | generic Finding Value fallback |

Each driver carries `score` (0..100) and `equity_weight` (weights sum to 1 per
finding type), and `overall_value_score = Σ score × equity_weight`. Every event
carries `epistemic_level` + `provenance`, consistent with the rest of the
intelligence program.

## Runtime

- Emitter: `tools/emit_value_driver_score.py` maps a finding to the scored event
  and, with `--emit`, writes an event/receipt/payload bundle to the state spine.
- Validation: `tools/tests/test_value_driver_seam.py` validates the schema, the
  committed example, and the emitter's scoring against the schema.

## Where it sits

Third connective seam of the intelligence program: Crystal Atlas (contract/
competitive intel) → **value drivers** (this seam) alongside the Web Intelligence
lane (`contracts/web-intel`), all warranted and on one evidence spine.
