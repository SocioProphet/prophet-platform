# Michael Attribution Deltas

## Purpose

This note records the Michael-specific causal-attribution delta vocabulary for the eval-fabric governance plane.

## Delta fields

The intended Michael-facing attribution surface SHOULD distinguish at least:
- `belief_delta`
- `rule_delta`
- `law_delta`
- `constraint_delta`

These sit alongside broader fields such as `model_delta` when present.

## Why this matters

Michael does not collapse all epistemic change into one undifferentiated score.

The eval-fabric plane should therefore be able to express:
- change in probabilistic belief state
- change in soft-rule influence
- change in candidate or promoted law influence
- change in asserted constraint influence

## Runtime implication

The existing `/v1/models/{model_release_id}/attribution` route can already carry an `attributions` object. This note and the accompanying schema define the expected Michael-facing shape for that object when the machine-science lane is active.
